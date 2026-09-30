# Bulk data through the bucket (tool/bucket-sync)

State: in use; measured; gates below. Michael approved replacing the IAP tunnel for bulk data (2026-09-30).

## Why

Syncs, fetches and pushes to the boxes went through the IAP tunnel (rsync over ssh). A fresh copy's sync took
minutes, fetches felt slow, and ssh dropped under load ("server not responding"). Measured on 2026-09-30:

- **The slow link is the laptop's uplink, not IAP.** A 100 MB upload straight to the bucket (JSON API) ran at
  1.3 MB/s (one stream) and 1.9 MB/s (8 streams); an unseeded 0.85 GB rsync through IAP ran at 1.8 MB/s. Downloads
  run at 22-28 MB/s from the bucket and 13-16 MB/s through IAP. No path makes new bytes go up faster; the win is
  never sending bytes a box or the bucket already has.
- **Uploads wreck everything else.** While an upload saturates the uplink, a 62 MB board fetch through IAP took
  8.1-9.5 s (4.4-5.3 s quiet) and one attempt dropped after 123 s with `Timeout, server <the render box> not responding`,
  the reported failure. The same fetch from the bucket took 2.6-3.8 s under the same load. rsync's minutes-long
  fresh-copy uploads were what saturated the uplink.
- **rsync's seeding was luck.** A fresh copy is seeded on the box by `cp -al` from the most recently synced copy;
  the sync then costs whatever differs from that one copy: 5.6 s on the render box (a similar seed), 304 s on the
  build box (a different seed), 465 s with none.

## Design (charkit/bucketsync.py; infra/gcp/build.sh sync, fetch, push, pull, verify)

A content-addressed store in the boxes' existing bucket (its name comes from the env files, never the repo).
Control stays on IAP: one ssh per transfer tells the box which manifest to apply. Standard library only; the box
runs the same file with its system python3, sent on the ssh's stdin (a box with no copy can still run it).

- **Store.** A blob per file content: `cas/<aa>/<sha256>`, uploaded with `ifGenerationMatch=0` (never overwritten).
  A manifest (JSON: path, sha, size, exec bit, mtime; symlinks; the ignored paths; whether i3d was sent) is itself a
  blob, `cas/m/<sha>`. Named pointers `cas/n/<name>` hold a manifest's sha for trees a box publishes (a gate's
  report, a build's outputs). One store for every worktree and both boxes: content one sync sent, no sync sends again.
- **Transport.** The GCS JSON API over kept-alive HTTPS connections from a shared pool, 16 threads on the laptop, 32
  on the box; a blob over 8 MB downloads in ~4 MB ranged slices (a lone 21 MB npz was a fetch's tail: 18 -> 22.6 MB/s).
  Measured faster than the gcloud CLI on every operation (table below). Credentials: the laptop user's
  (`gcloud auth print-access-token`, cached in `~/.cache/charkit/bucketsync/token.json`, mode 600, until its
  tokeninfo expiry; a 401 refreshes it) and the box's service account (the metadata server). Nothing new is opened:
  the box already reached the bucket (`remote.put` used it for files over 100 MB).
- **Sync** (`build.sh sync WT`). The laptop lists exactly what the rsync sent: tracked and untracked-not-ignored files
  on disk, `charkit/out/i3d`, `charkit/out/remote/*.json`, nothing under `.git`, `__pycache__` or `.cache` (checked
  against an rsync dry run: identical lists, 956 files on a sparse worktree, 958 on pipeline-3d's). It hashes them
  (a stat cache keyed on size, mtime and inode: 0.0-0.5 s), learns which blobs the bucket lacks (a local record of
  known blobs, then one metadata call each for up to 256 unknown, else a listing), sends a small gap itself (up to
  4 MB) and writes the manifest. The box then:
  - fetches blobs its cache (`/srv/work/.cas/blobs`) lacks from the bucket, inside GCP (884 MB into a cold cache in
    6.2 s);
  - **adopts** a blob the bucket lacks from its own copies (a file at the same path, same size, sha256 checked),
    copying it into the cache and uploading it from the box; only blobs no box copy has are reported back, and the
    laptop sends those and reruns. The first sync of this worktree, with the bucket empty, adopted 953 of 957 blobs
    and sent 0.1 MB: 13.4 s;
  - links each input from the cache (read-only files, `<sha>.x` for the exec bit since links share a mode), replacing
    by rename, so nothing is ever written through a link; a write into an input fails loudly instead of reaching
    every copy that shares it;
  - deletes what the manifest no longer names, under rsync's excludes (`charkit/out/*` except `i3d` and
    `remote/*.json`, `.git`, `__pycache__`, `.cache`, the laptop's ignored paths), and empty directories;
  - drops a changed `.py`'s bytecode (keyed on the old file's mtime and size);
  - keeps the i3d rule: a worktree without `charkit/out/i3d` leaves the copy's own, or seeds it by links from the
    box's fullest;
  - drops cache blobs no copy links any more (link count 1) after 3 days.
- **Fetch** (`build.sh fetch WT PATH`). The box publishes PATH (hashes, uploads missing blobs, stores the manifest),
  the laptop downloads only what differs (same size and mtime, or same sha, stays) to a temp file beside each target
  and renames it over: an output is never linked and never written through (charkit's cache.unshare lesson). No
  deletes, as rsync's fetch had none. `remote build` and `remote gate` publish inside their own ssh (the script is
  installed from that ssh's stdin as `/srv/work/.cas/bin/bucketsync-<sha12>.py`), so their outputs come back with
  no second connection through the tunnel: the laptop pulls by name.
- **Push** (`build.sh push LOCAL REMOTE [--link]`). rsync's semantics (a trailing slash sends a directory's contents,
  no deletes). One-off files (git bundles) are copied into place, not kept in the cache; `--link` is for inputs (the
  gate's i3d).
- **Verify** (`build.sh verify WT`): the box's copy against the worktree, file by file (missing, content, exec bit,
  symlinks, managed files that should have been deleted).
- **Log.** Each transfer appends a line to `~/.cache/charkit/bucketsync/log.jsonl` (files, bytes, blobs and bytes
  sent, seconds per phase).
- **Fallback.** `CHARKIT_SYNC=rsync` keeps every command on the tunnel as before. No automatic rsync for small syncs:
  the bucket sync was faster there too (1.6-1.9 s against 2.5-2.7 s), since rsync's path costs two ssh connections.

## Measurements (2026-09-30, the laptop and both boxes, one session)

Bench worktrees are fresh `tools/worktree.sh` copies of pipeline-3d (charkit profile, 955-957 files, 884 MB).
"Before" is build.sh's rsync over IAP; fetch rows interleave rsync and bucket runs in the same minutes.

| operation | before (rsync over IAP) | after (bucket) | speed-up |
|---|---|---|---|
| fresh copy, build box (seeded from a different copy) | 304.3 s | 3.2 s | 94x |
| fresh copy, no seed (a box with no similar copy) | 465.4 s | 3.2 s (bucket warm), 13.4 s (bucket empty, box adopts) | 35-145x |
| fresh copy of content no box or bucket has yet | uplink-bound, ~1.8 MB/s | the same, once: the bucket keeps it for every worktree and box | 1x |
| fresh copy, render box (seed happened to match) | 5.6 s | 8.3 s (cold box cache) / 3.2 s (warm) | 0.7-1.8x |
| second fresh copy, build box | - | 1.7 s | |
| sync, nothing changed | 2.5 s | 1.6 s | 1.6x |
| sync, 3 files changed | 2.7 s | 1.9 s | 1.4x |
| board build outputs, render box (48 files, 62 MB), quiet uplink | 4.4 / 5.3 / 5.0 s | fetch 6.4 / 5.0 / 4.5 s; pull after an in-session publish 2.7-2.9 s | 1.0x (fetch), 1.7x (pull) |
| the same, uplink saturated by an upload | 9.5 / 8.4 / 8.1 s; one run dropped after 123 s | pull 2.6 / 2.7 / 3.8 s | 2.2-3.6x, no drops |
| build outputs, build box (35 files, 33.5 MB) | 2.4 / 4.1 / 12.0 s | fetch 4.8 / 3.6 / 3.6 s | 0.5-3.3x |
| gate report (2 files, 59 KB) | 1.5 / 1.4 / 1.8 s | pull after the in-session publish 0.6 / 0.8 / 0.6 s (publish on the box: 0.1 s) | 2.3x |
| fetched again, nothing changed (62 MB board) | 1.5 s | 2.0 s | 0.7x |

Raw links: upload to the bucket 1.3 MB/s (one stream) / 1.9 MB/s (8 streams); download 25.6 MB/s (one stream) /
28.0 MB/s (sliced) / 24.6 MB/s (8 files); IAP ssh round trip 1.2 s. gcloud CLI against this module's JSON API: an
existence check 0.64-0.88 s against 0.20 s (process start and TLS included); 8 x 8 MB down 4.8-8.8 s against
2.3-2.6 s; 100 MB down 8.4 s against 5.7 s.

**Against the 5x target.** Fresh-copy syncs: 94x and more on the build box. Output fetches: not 5x on a quiet
tunnel. A 62 MB board is incompressible (npz, png, blend; zlib saves 5%) and shares ~15% of its bytes with other
board builds, so it's bound by the laptop's ~25 MB/s downlink: 2.5 s is the floor against rsync's ~4.9 s. The
bucket's real gains on fetches are no second ssh (the in-session publish), immunity to a saturated uplink (2.2-3.6x,
no drops), and syncs that no longer saturate the uplink in the first place.

**Correctness.** `verify` after every bench sync: 955 files, missing 0, content 0, mode 0, extra 0 on both boxes.
The bucket-fetched board and build outputs matched rsync's byte for byte (`diff -r`). 10 unit tests
(`charkit/tests/test_bucketsync.py`, a directory standing in for the bucket): the file list follows build.sh's rules;
links are read-only and shared; a change never reaches another copy; the box's outputs, bundles, caches and ignored
paths survive a sync while dropped files go; the i3d rule; missing blobs are reported; adoption; publish and pull
never write through a link; pushes; `check` finds what a copy gets wrong.

**Mixed use.** Worktrees that haven't merged this still rsync. rsync never writes through a link (it renames), so
contents are safe, but `rsync -a` chmods unchanged files in place: one rsync into a linked copy made 949 cache blobs
writable. The cache makes a blob read-only again whenever it's reused.

## Gates and daily use

Gates of 1498b07 (the code; later commits are these notes) into pipeline-3d e11fadb, on the build box, both through
the new transport (the bundle pushed through the bucket, the i3d pushed as linked inputs, the report published in
the gate's ssh and pulled):

- default spec: **PASS**, no check changed, every test file ok (`test_bucketsync.py` included, on the box's Linux
  Python). Bundle push 2.2 s (1 file, copied, not cached); i3d push 551 MB in 2.2 s, nothing sent, nothing placed
  (the seed's links were already the cache's); report pulled in 0.4 s.
- `--spec charkit/spec/clawd_mh.json`: **PASS**, no check changed. i3d push 1.6 s; report pulled in 0.5 s.

A real board build on the render box (`remote --box render build charkit/spec/clawd.json --boards views,body`), this
worktree's first copy there: sync 2.9 s (958 files, 884 MB; 2 blobs, 0.1 MB sent), the build 10.5 min, its outputs
published in the build's ssh and pulled: 47 files, 53 MB in 5.0 s. An rsync checksum dry run against the box: 0
files differ.

tool/bucket-sync merges cleanly into pipeline-3d (120d197) and with tool/infra (whose remote.py change is 2 lines).

## Open items

- **Bucket garbage collection.** Blobs and manifests accumulate (about 0.9 GB now; the bucket keeps deletes 7 days
  under its soft-delete policy). A `gc` that keeps what the last N days' manifests name is straightforward; not
  written.
- **Fetch latency at the downlink's floor.** Getting a board to the laptop 5x faster than rsync means not waiting for
  it at the end: the box could publish outputs as a build writes them and the laptop pull during the build, leaving
  only the last files after it ends. Or fetch less: each board build carries a `.blend1` (Blender's backup of the
  previous save, 9.7 MB of 62).
- **The login still gates everything.** Control stays on IAP, and the bucket path uses the laptop user's token, so an
  expired gcloud login still stops every box command (bucketsync says so and exits).
- **The handoff's "How the gate gets its code" bullets** (files over 100 MB through the bucket; the first sync seeded by
  hard links; i3d rsynced) describe the rsync path, now the `CHARKIT_SYNC=rsync` fallback. For the integrator to
  update at merge.
- **Worktrees on the old build.sh** keep rsyncing until they merge this. Their seeding may `cp -al` a bucket-synced
  copy (links into the cache); rsync renames rather than writing through, and the cache re-asserts read-only modes.
- **One ssh per command.** An IAP ssh costs 1.2-3.8 s; `remote build` still makes several (up, keepalive, sync, run).
  ssh multiplexing (ControlMaster) would cut them to one, at the risk that a dropped master takes every session with
  it; worth measuring now that bulk data is off the tunnel.
