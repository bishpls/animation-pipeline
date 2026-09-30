# A shared cache for produced references (tool/produced-cache)

State: implemented and unit-tested; box measurements in progress (see "Measurements").

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

## Measurements

(in progress)

## Open items

(in progress)
