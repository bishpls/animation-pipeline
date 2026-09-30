# A shared cache for produced references (tool/produced-cache)

State: done; measured on the build box; final gates below. Numbers are from the build box.

## Why

A gate takes 14 min median (p90 29). Its candidate build takes 355 s of wall time against 166 s traced; most of the
gap is the produced references rebuilt from scratch in every fresh gate clone: the hull (170-220 s), the outfit's masks
(70-120 s) and the hair layers (about 30 s). 52% of gates reuse a cached baseline, so their candidate pays all of it,
and so does every fresh box copy. Since tool/stamp-spec a stamp covers a reference's file inputs (the TRELLIS field
included), its spec sections and its producer's code one import deep, so reuse keyed by stamp is safe.

## Design (charkit/manifest.py)

- **Where.** `manifest.produced()`, when a reference is missing or stale in this copy, looks in a shared cache before
  building: `CHARKIT_PRODUCED_CACHE`, default `~/.cache/charkit/produced` (per user; a box's gates and copies run as
  one user, so they share it). `CHARKIT_PRODUCED_CACHE=off` turns it off.
- **Key: `RID/STAMP-CODE2`.** `code2()` digests the producer's code closure two imports deep (`CACHE_DEPTH = 2`,
  against the stamp's `STAMP_DEPTH = 1`), the code2 of each produced reference it reads, and the Python, numpy and
  machine. A branch that changes code two imports down misses; a miss only rebuilds, as before.
  - *The reads' code2 folded in*: the hull reads the outfit's masks. With only its own code in the key, an outfit
    change two imports down would rebuild the masks (their key changed) while the hull hit an entry made from the old
    masks (the hull's stamp holds the outfit's stamp, which is one import deep).
  - *The machine in the key*: hulls differ across CPUs (tool/hull-det). The default cache is per machine anyway;
    this keeps a cache pointed at shared storage from mixing them.
- **What's cached.** Exactly the files the build wrote: the reference's folder is listed (size, mtime, inode) before
  and after the build, and the new or changed files are stored, with `PATH.stamp` and `PATH.stamp.json`. The lock and
  the cut-down spec (`PATH.spec.json`, written by `produced()` before the lookup, so a hit has it too) aren't.
  The hair layers share `charkit/out/clawd/hair/` with other outputs; the hull's page (`img/`, `index.html`) left by an
  earlier full run isn't the fast path's and isn't stored.
- **What's read first.** `produced()` now produces a reference's produced reads before its own lookup (the hull
  its outfit masks), so the build time the entry records is its own (the hull's build used to build the masks inside
  it).
- **Restore by copy** (never a link: builds rewrite outputs), each file hashed as it's copied into a temporary beside
  its target; only when every file matches its sha256 are they renamed into place, the stamp last (a restore cut
  short leaves the reference stale, not wrong).
- **Store atomically.** Files go into `KEY.tmp-PID/files/` with `entry.json` (each file's size and sha256, the build's
  seconds, the copy that made it), then `os.rename` into `KEY`. If `KEY` exists (another gate won the race), ours is
  discarded.
- **Damaged entries.** A missing file, a size or sha256 mismatch, an unreadable `entry.json`, a record for another
  key or a path leaving the folder: a miss, and the entry is deleted (renamed aside, then removed).
- **Prune.** The newest 30 entries per reference by last use (a hit touches its entry), `CHARKIT_PRODUCED_CACHE_KEEP`.
  At about 18 MB for all three references, that's about 0.55 GB at most. Leftovers of stores cut short go after an
  hour.
- **Logs.** Each hit and miss prints a `CHARKIT_PRODUCED` line with the time saved or spent, for example
  `CHARKIT_PRODUCED hull: hit 8f3aa839-1c2d3e4f: 7 files, 7.7 MB restored in 0.1 s (its build took 187.2 s: 187.1 s saved)`,
  and appends an event to `ROOT/events.jsonl` (rid, key, hit or miss, seconds, the copy's path, host).

## How much the key's depth costs

The code the key covers (`cache.code_units`, charkit's 103 modules):

| reference | depth 1 (stamp) | depth 2 (key) | depth 3 | all |
|---|---|---|---|---|
| outfit_masks | 5 | 9 | 23 | 81 |
| hull | 14 | 33 | 40 | 81 |
| hair_layers | 1 | 5 | 23 | 81 |

Against the last 39 merges into pipeline-3d (each merge's diff; today's closures):

| reference | the stamp changed (depth 1) | only the key changed (depth 2) | neither |
|---|---|---|---|
| outfit_masks | 16 | 6 | 17 |
| hull | 22 | 6 | 11 |
| hair_layers | 1 | 14 | 24 |

Depth 2 costs 6 extra outfit misses and 6 extra hull misses in 39 merges. 10 of 39 merges touched none of the three
closures. Within a branch's own gates (a second gate of the same branch, a spec change, a box copy of the same code)
the key doesn't move at all.

## Tests (charkit/tests/test_produced_cache.py)

A fake producer (a command whose code is three temp modules, `charkit.fakeprod` → `fakemid` → `fakedeep`, patched
into `cache._module_file`; its output carries random bytes, so a restored file can only have come from the cache):

- a hit restores the producer's files byte for byte, by copy (another inode, one link; writing it leaves the entry
  whole), and logs the time saved;
- only the producer's files are cached: an older file in the folder and an unrelated output are neither stored nor
  touched;
- an edit two imports down keeps the stamp and changes the key (a fresh copy misses and rebuilds); a reader's key
  follows the code of what it reads;
- a change in a declared spec section misses; switching back hits; a knob outside the sections hits;
- a flipped byte, a missing file, a truncated file, a garbled `entry.json`, a record for another key and a path
  leaving the folder are each a miss, the entry deleted and the rebuild stored;
- eight processes storing one key at once: one `stored`, seven `exists`, one whole entry from a single writer, no
  temporaries left;
- the prune keeps the newest three of five and clears an old leftover;
- `off` turns it off;
- on the real manifest, each Clawd reference's key covers more modules than its stamp.

`test_manifest.py` runs with the cache off: its tests are one copy's own staleness and rebuilds.

## Measurements (build box, 17da469 into pipeline-3d 2e3bdd5)

### Gates: the same branch twice

Both 2e3bdd5 baselines were cached, so each candidate ran in a fresh clone (the 52% case).

| gate | produced references | candidate build, wall | its CPU | Blender + QA (traced) | the whole gate |
|---|---|---|---|---|---|
| 1: default spec, empty cache | 3 misses, stored: outfit 56.6 s, hull 100.5 s, hair layers 26.6 s (183.7 s) | **436.1 s** | 662.7 s | 155.6 s | 9:43 |
| 2: default spec | 3 hits, restored in 0.03, 0.03 and 0.01 s | **288.9 s** | 403.8 s | 167.5 s | 7:09 |
| clawd_mh spec | 3 hits (the same keys: its cut-down sections are clawd.json's) | 159.5 s | 249.9 s | 139.3 s | 5:30 |

For the default spec's candidate, wall time fell by 147.2 s (34%) and CPU by 258.9 s (39%). All three gates PASS with
no check changed and all 31 tests ok. Gate 2's events (`~/.cache/charkit/produced/events.jsonl` on the box):

```
{"built_seconds": 56.6, "event": "hit", "rid": "outfit_masks", "saved_seconds": 56.6, "seconds": 0.03, "files": 6, "bytes": 7502962, ...}
{"built_seconds": 100.5, "event": "hit", "rid": "hull", "saved_seconds": 100.5, "seconds": 0.03, "files": 9, "bytes": 8031414, ...}
{"built_seconds": 26.6, "event": "hit", "rid": "hair_layers", "saved_seconds": 26.6, "seconds": 0.01, "files": 5, "bytes": 3095880, ...}
```

The stored files: outfit (6) `outfit_masks.npz`, `outfit_graph.json`, `outfit.png`, `outfit.md` and the two stamps;
hull (9) `hull.glb`, `hull.glb.json`, `hull.json`, `hull.npz`, `hull.ply`, `hull_labels.npy`, `hull_pieces.npy` and
the stamps; hair layers (5) `hair_layers.npz`, `hair_layers.json`, `breakdown_families.npy` and the stamps.

### A fresh box copy

`charkit build charkit/spec/clawd.json --no-blend` in a box copy holding only `charkit/out/i3d`, each run from a fresh
state (no produced references, no `charkit/out/.cache`):

| run | produced cache | produced references | wall |
|---|---|---|---|
| cold | empty | 3 misses: 65.6 + 137.7 + 32.3 = 235.6 s, stored | **579.9 s** |
| control | off | built | 529.6 s |
| warm | the gates' | 3 hits: 0.3, 0.6 and 0.0 s | **309.1 s** |

From cold to warm, the wall time fell by 270.8 s (47%).

In a gate log, a hit reads `CHARKIT_PRODUCED hull: hit 4b7d356f-0ff600a0: 9 files, 8.0 MB restored in 0.6 s (its
build took 100.5 s: 99.9 s saved)`; a miss reads `CHARKIT_PRODUCED hull: miss 4b7d356f-0ff600a0 (no entry), building`,
then `CHARKIT_PRODUCED hull: built in 137.7 s; stored 4b7d356f-0ff600a0: 9 files, 8.0 MB`.

### Bit identity

- **Produced references.** The cold copy's from-scratch build was compared entry by entry with gate 1's clone's
  (same keys). The outfit (6 of 6 files) and the hair layers (5 of 5) are identical. The hull matches on 8 of 9:
  `hull.glb`, `.npz`, `.ply`, the labels, the pieces, the sidecar and the stamps. `hull.json` differs only in its
  `seconds` (the build's own time), which also differs between the two from-scratch builds (cold and control).
- **The builds' QA.** `charkit.boarddiff` finds 16 images with 0 different and 217 QA checks with 0 different for
  cold against warm, control against warm, and cold against control.
- **What else differs:** `qa.json` in `measured.seconds` and `measured.bundle` (the bundle's digest). In the bundle,
  2 of 742 arrays differ: `o/clawd_skin/masked/V` (2 vertices) and `masked/shrink` (1 value), by at most 7.45e-9
  (a float32 last bit). The out folder's paths and the timestamp differ too. The same two arrays differ by the same
  amount between two from-scratch builds (cold and control), so this is the Blender stage's run-to-run jitter, not the
  cache.

### The per-copy build cache, for the follow-up

The same box copy built again with its own `charkit/out/.cache` warm (142 MB) and its produced references fresh:
**206.1 s**, against 309.1 s with only the produced cache warm, so about 103 s (33%) more for a fresh copy of the
same code. That's with some steps still re-running:
- `pieces_hair` ("its input changed": its key holds the out folder's path);
- `bundle` ("no entry for this code");
- the QA's `shape` and `look` (the skin-mask jitter above: 4.9 s and 22.2 s);
- the QA's `hair_pieces` (the out path in `spec.hair`).

In the warm build, the remaining time splits into Blender stages 65 s (character 30, garments 9.4, bundle 6.7, hair
5.0, face shading 4.4), QA 96 s (sheet_pieces 25, look 22, sheet_body 18) and about 148 s of venv steps before
Blender: fit, `code_head`, `code_body`, geom and pieces hair. A gate whose branch changes code mostly misses the stage
keys (they take the whole transitive code), so that saving would land on re-gates of the same branch and on fresh
copies.

## Open items

- **Gate reports don't show the CHARKIT_PRODUCED lines.** `gate.py`'s `_build` captures the build's output and keeps
  its tail only on failure, and the remote gate deletes its log. The lines above come from the build logs and the
  cache's `events.jsonl`. A three-line change in `gate.py` would lift them into `rep['cand_build']['produced']`: grep
  `CHARKIT_PRODUCED` in `r.stdout`. It's outside this branch's files, and gate code runs from `into`, so it would take
  effect once merged.
- **A shared stage and file-step cache** (`charkit/out/.cache`, per copy today; about 103 s on a fresh copy, measured
  above). The misses to fix with it: the out folder's path in `pieces_hair`'s and the QA `hair_pieces`' keys, and
  the bundle's "no entry for this code".
- **The skin mask's last-bit jitter** (`o/clawd_skin/masked/V`, `masked/shrink`, 7.45e-9) makes bundles differ run to
  run and defeats the QA cache for `shape` and `look` (27 s). A hull-det style fix (ordered reductions) would make
  whole builds bit-identical.
- **A missed input now spreads.** An input a producer reads but doesn't declare used to give copies different outputs
  under one stamp (the TRELLIS field). With a shared cache, the first copy's output is served to every copy on the
  box. A verify mode (on a hit, build anyway and compare the sha256s, as `build --cache verify` does for stages) would
  catch that. It isn't built.
- **A module-based producer's stamp is shallower.** `code_units(modules=(M,), depth=1)` is the module alone:
  hair_layers' stamp covers `hairlayers.py` only, not `outfit.py` and the rest it imports (a function-based producer's
  depth 1 includes its imports). The cache key's depth 2 covers them. In one copy, though, an edit to `outfit.py`
  still doesn't restamp the hair layers. This predates this branch; declaring `produced_fn: charkit.hairlayers:produce`
  would make the stamp one import deep like the others (it would restamp once).
- **`hull.json` carries its build's seconds**, the only byte that differs between two hull builds. A restored hull
  carries the storing build's time. Harmless.
- **Per machine.** The default root is per user and per machine (the laptop and the box never share), and the key
  holds the machine, Python and numpy. At 30 entries per reference, it's at most about 0.55 GB.
- **Box leftovers** (removable): `/srv/work/pc-measure` (logs, the cold cache, sha lists), `/srv/work/pc-measure.sh`,
  `/srv/work/pc-control.sh`, and the copy `/srv/work/animation-pipeline-prodcache` with `charkit/out/pc_cold`,
  `pc_warm`, `pc_scratch` and `pc_stagewarm`.

## Final gates (ff2933b: this branch merged with pipeline-3d b8097cf, into b8097cf)

Paused before the verdicts arrived (usage limit). Both were launched at 02:54 EDT, run in parallel on the build box,
and fetch their reports on their own when they finish:
- default spec: `charkit/out/gate/gate_tool-produced-cache_ff2933b_into_b8097cf.md` (and `.json`)
- `--spec charkit/spec/clawd_mh.json`: `charkit/out/gate/gate_tool-produced-cache_ff2933b_into_b8097cf_clawd_mh.md`
  (and `.json`)

The same reports are on the box under `/srv/work/_gate/tool_produced-cache-*/`, and the candidates' outputs are in
`/srv/work/gate-out/cand_tool-produced-cache_ff2933b_into_b8097cf*`. The cache's side is the tail of
`~/.cache/charkit/produced/events.jsonl` on the box. b8097cf's hull code changed (hull-det), so both candidates miss on
new keys and store at about the same time (a real race: one `stored`, the other `exists`). If they aren't there, re-run
them. pipeline-3d has since moved to 53a557f (face and eyes); the coordinator will merge after a check.
