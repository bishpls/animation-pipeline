# Incremental builds and checkpoint gating (design)

Status: design (incremental round 1, tool/incremental, 2026-10-01). Parts 1 and 2 aren't implemented; round 1 landed
the three infra calls they build on (the budget's blocking rule, the QA's drawing on a GPU, the iterate profile as the
QA-only default). The follow-up rounds and their acceptance are at the end.

Michael, 2026-10-01: "the current build step is really quite inefficient, so fixing that is high priority ... gating on
checkpoints rather than gating on every single subagent process change."

## 1. What a change costs today (measured)

Every iteration is a monolithic build: every piece regenerated, every QA part re-run, on a remote box, whichever knob
changed. A gate is two such builds plus the test suite and, when measuring code moved, the 2x2's two crossed QA runs.

| measure (default spec, gate conditions: threads 4, `--boards '' --no-blend`) | value | source |
| --- | --- | --- |
| build CPU, 09-30 evening gate baseline | 577 s (334 s wall) | infra5o, `profile base_25b1936` |
| build CPU, 10-01 16:59 gate baseline | 1310 s (787 s wall) | infra5o, `profile base_25ff0f25` |
| build CPU, today's default (batch4 gate 3's candidate, venv steps run, build2) | 1455 s (840 s wall) | gate_merge-batch4_d5a916a7 |
| of which the QA | 924 s CPU (~400-600 s wall) | the same; 1090 s on 25ff0f25 |
| of which Blender (character 49, look export 56, the bundle, garments) | 211 s | the same |
| of which the cached venv steps (pieces_hair 181, hair_select 60, code_head 52) | 320 s | the same (a gate's baseline restores them) |
| a gate, wall | 15.6 min median (9.6 on 09-30) | the brief |
| a build, wall | 13.9 min median (8.5 on 09-30) | the brief |

Where the QA's CPU goes (infra5o's cold profile b0, 1192 s of 1790): `declared` 364 (Michael's flags as declared
checks), `look` 192, `artifacts` 141, `face_flags` 93, `motion` 45-120, `face_region` 44, `skirt` 39, `hair_noise` 38,
`scalp` 34, `hands` 33. Under cProfile the render-heavy parts spend most of their time in the toon renderer drawing on
the CPU box's software rasteriser (llvmpipe/lavapipe: `submit`'s worker threads), the picture 4 x 4 supersampled over
the 2.03M-triangle look export: declared 7 frames 80 of 136 s wall, look 22 frames 40 of 68, artifacts 4 frames 33 of
45, face_flags 5 frames 13 of 40. No frame is drawn twice in a pass (a cross-part frame memo wouldn't pay); culling the
frame's window saved nothing (lavapipe's cost is fragments). Blender is 1-4% of box CPU.

So a one-knob change (a collar width, a hair lock's twist, a finger's curl) costs 12-15 min of wall and ~1400 s of CPU
before anyone sees a number, and ~25 min more to gate. The piece it touched is a few percent of that work.

Round 1's measurements (QA drawn on the render box's L4, the iterate profile's saving) are in section 8.

## 2. Part 1: incremental builds

### 2.1 A content-addressed stage graph at piece granularity

**Today.** charkit/cache.py keys each Blender scene stage (character, hair, face shading, garments) by what it read
while it ran (spec keys at any depth, upstream values key by key, Blender objects, files by sha256, the code closure as
syntax trees, plus `cache.ran`'s runtime record of the code that actually ran), and each venv step (`file_step`: code
head and body, hair select, hair pieces, garments geom) and QA part the same way. A stage is the unit: the garments
stage builds all 19 garment objects, so a collar knob rebuilds the shorts; the hair pieces step builds every lock.

**Proposed.** A graph whose nodes are (stage, piece) and whose edges are recorded reads:

- **Node key** = digest of (the spec subtree it read, recorded as today; its code closure: the static walk, which since
  b22652e5 follows literal runtime imports, plus `cache.ran`'s record; the content hashes of the upstream node products
  it read; the files it opened). Computed before running from the previous run's recorded reads, as file_step does.
- **Node product** = the piece's arrays (vertices, faces, attributes, materials) as one `.npz`, stored by its own
  content hash. Two keys that produce the same bytes share a product (early cut-off: a knob change that doesn't move
  the collar's vertices stops there).
- **Pieces**: the outfit graph's pieces (bodymeasure.piece_map), the hair pieces and locks (geom/hairpieces), the
  accessories, the face features, the body and head. The venv builders already produce most of them as arrays
  (geomstage, hairpieces, code_head, code_body); Blender's stages become assembly of stored pieces plus the steps that
  need Blender (modifiers, the rig, shading), each keyed per object.
- **Downstream**: the bundle and the look export are per-object products (bundle.py and gltf.py already write per
  object); a piece's change rewrites its objects only, and the export's per-primitive hashes are what the QA's frame
  keys read (2.2).
- **The dynamic-import fix and the stale-key net** (infra5o, b22652e5): literal runtime imports followed by the walk,
  the runtime record checked on restore (`cache.ran_changed`), `--cache verify` comparing products with what a lookup
  would restore. The static lint of section 4 makes a key's blind spots a test failure.

### 2.2 QA checks declare what they read; renders cached per piece and view

**Today.** Each QA part is cached on what it read of the bundle, but the render drawing reads the whole export file, so
any geometry change re-runs every drawn part (declared, look, artifacts, face_flags, hair_noise, scalp: ~900 s CPU on
the CPU box).

**Proposed.**
- Each check declares its reads: pieces (names or the outfit graph's kinds), views (front, three_quarter, profile,
  back, the head frames), drawings (the render frame's window, light, line width) and design-side inputs. `declared.py`
  already has the piece and view of every declared check; registry parts gain a `reads` declaration, checked at run
  time (a part that touches a piece it didn't declare fails its test, as denominators do for counts).
- **Frames as nodes.** A frame's key = (window, light, line width, picture or buffers, supersampling, the adapter
  class, and the content hashes of the export primitives inside its window: buffers._cull already computes which
  primitives a window can see). Frames are stored (the buffers are what the checks read); a collar change redraws the
  frames whose window holds the collar, and only the checks reading those frames re-run.
- The design side is already memoised per argument (`Design.memo`, venv_memo); it stays.
- A check's product is its row in qa.json, keyed by (its code closure, the frames and pieces it read). An incremental
  QA writes the full qa.json, restored rows and fresh ones alike, with per-row provenance (restored from key K, or
  measured).

### 2.3 The local piece studio

One piece regenerated in-process on the laptop (numpy builders, no Blender), drawn by charkit.render (wgpu on Metal;
its EEVEE parity and the laptop-vs-box parity are measured: 71 of 73 drawn checks identical, the 2 others rasteriser
ties), with that piece's declared checks live. Seconds per tweak.
- `python -m charkit studio SPEC --piece collar [--knob path=value ...]`: loads the last full build's stored pieces
  (the graph's products), rebuilds the named piece and its dependants in-process, writes a look export of the touched
  primitives into the stored export, draws the frames the piece's checks read, and prints the checks with their shape
  IoU in every view (the guard).
- A browser view (engine/three/charkit/look.js on the export) for eyeballing beside the numbers.
- `sweep optimize` gains a `studio` stage adapter: a row = one in-process piece rebuild + its checks (today's `qa`,
  `garments`, `hair`, `face` stages splice bundles; the studio stage would use the graph's real builders).
- Blender stays for full builds, boards and gates. The studio's numbers are verified against a full build at the
  checkpoint (section 4, layer 3).

### 2.4 Measure everything

Per iteration: wall and CPU for a one-knob change (a collar, a hair lock, a hand) before and after, on the laptop and
the box. Correctness: the incremental result equals the cold build's, bit for bit or within a declared tolerance per
product (an `.npz` by its arrays, qa.json by values and statuses), with verify mode in CI.

## 3. Part 2: the gate workflow (checkpoint gating)

1. **Quick gate per merge (minutes).** Unit tests first (fail fast: infra5o), then an incremental build of the
   candidate against the integration branch's stored graph, only the affected checks re-run, the anti-gaming guard on
   the touched pieces (their shape IoU in every view), the flags those pieces carry, and layer 2's sampled verification.
   Blocks on: new FAILs among the affected checks, flag regressions on touched pieces, the guard, a failing test, a
   stale key found by sampling. Merges land on an integration branch.
2. **The coordinator's rolling integration build.** After each quick-gated merge, an incremental build of the
   integration branch and a review page for Michael: what changed since the last checkpoint, per piece, at matching
   scale, with the numbers, and each stage's last-verified time (layer 2's coverage).
3. **Checkpoint gates (full policy K)** at milestones or on a cadence the coordinator calls: a cold full build, every
   check, the calibration records, the CPU budget (the round 1 rule), the 2x2 remeasure rule, and layer 3. A failing
   checkpoint **bisects** the merges since the last one: each candidate point is an incremental build (cheap: the graph
   shares everything below the merge that changed it), the culprit named, reverted or fixed.
4. What moves from every merge to checkpoints: the CPU budget, calibration-record completeness, untouched-piece drift
   (a check on a piece no merge touched that moved: a stale key or a shared helper), the full 2x2. charkit-worker.md's
   Gates section and the handoff get the new workflow when round 5 lands.

## 4. Verification that stays cheap (three layers)

Michael: "Can that match-a-full-build check actually be run quickly?" Not a cold build per iteration:

1. **Static lint (seconds, every test run).** Scan stage and QA code for reads a key can't see: computed imports
   (`importlib.import_module(name)` with a non-literal name, registry discovery), file reads outside the recorded
   inputs (`open` of a path not derived from the spec or a recorded input), `os.environ` reads not in the key's env
   list, module-level mutable state read across stages. The test fails until each is recorded or made static (an
   allowlist with a reason per entry).
2. **Sampled verification (about a minute, per quick gate).** Re-run one or two restored nodes cold, picked at random
   weighted by how recently their code changed and how long since each was last verified, and compare product hashes
   (each node stores its product's hash). Over a day's merges every node is re-verified; a stale key surfaces within
   hours. Coverage (each node's last-verified time) on the rolling review page.
3. **Full verification at checkpoints (almost free).** The checkpoint's cold build compared node by node with the
   incremental build of the same commit (product hashes and qa.json rows).

Measure each layer's cost and what it catches: plant a stale key (a node that reads a file it doesn't record) and
record which layer finds it, how fast.

## 5. Risks and what doesn't change

- Blender's own nondeterminism (infra5's k: the masked skin's last-bit noise on loose vertices, fixed by no_loose)
  would break product hashes: the graph compares `.npz` products by arrays, and Blender-side nodes keep today's
  restore check (the trace's snapshot must equal the stored one).
- The renderer's results depend on the adapter (section 8): frame keys carry the adapter class, and gates compare like
  with like.
- Gates stay cold at checkpoints: incremental results are trusted between checkpoints only as far as layers 1 and 2
  verify them.

## 6. Follow-up rounds (lean), each with its acceptance

| round | scope | acceptance |
| --- | --- | --- |
| 2: the per-piece graph, venv side | node keys and products for the venv builders (hair pieces per piece and lock, garments per object, code head and body), early cut-off by product hash, the static lint (layer 1) | a collar knob rebuilds the collar's nodes only (the trace lists them); the incremental bundle equals the cold one array for array; the lint fails on a planted computed import and a planted untracked file read; CPU and wall for three one-knob changes before and after |
| 3: QA reads and frame caching | `reads` on registry parts and declared checks, frames as stored nodes keyed by their window's primitives, per-row provenance in qa.json | a collar knob re-runs only the checks that read the collar or its frames; incremental qa.json equals the cold one row for row on 3 one-knob changes; QA CPU for those changes before and after |
| 4: the piece studio | `charkit studio`, in-process piece rebuild and drawing on the laptop, the piece's checks and shape IoUs live, the optimize stage adapter | a one-knob change's loop under a minute on the laptop (target: seconds), its numbers equal to the box's full build within the parity bounds (render/parity.py) |
| 5: quick gate + rolling build | the quick gate (affected checks, guard, flags of touched pieces, layer 2), the integration branch, the rolling review page with layer-2 coverage | a quick gate in minutes on a real merge; a planted stale key caught by sampling, time-to-catch measured; the review page for the rolling build |
| 6: checkpoint gates + bisection | the checkpoint gate (cold, full K, layer 3), bisection over the merges since the last checkpoint, docs (charkit-worker.md Gates, the handoff) | a planted regression among 4 merges named by bisection with its cost measured; layer 3 comparing a checkpoint's cold and incremental builds node by node |

## 7. Round 1 (landed with this doc)

1. **The budget's blocking rule** (gate.budget_rule): block when the candidate's build CPU is more than 10% over
   charkit/budget.json's total AND more than 5% over its baseline's. Both read in build-box seconds (the box's
   CPU_SPEED, passed by `remote gate`) with each restored venv step counted at its cold cost (budget.json `cold`) and
   `resolve` at its restored figure when it built the shared produced references, so cache hits and misses don't move
   the figure. budget.json re-baselined on today's default. Test: test_gate
   `test_budget_rule_blocks_over_the_budget_and_the_baseline`.
2. **The QA's drawing on a GPU**: section 8.
3. **The iterate profile as the QA-only default**: `python -m charkit qa BUNDLE` runs 'iterate' (motion QA skipped,
   reported SKIPPED and announced as `CHARKIT_QA_PROFILE iterate: motion skipped`) unless `--profile full`; optimize's
   confirm builds pass `--profile iterate` unless a term or keep pattern reads a motion check, and leave the skipped
   part's checks out of their comparison on both sides (confirm.json `profile`, `skipped`). Builds and gates keep
   'full' (a gate's builds and its 2x2's crossed QA runs set CHARKIT_QA_PROFILE=full). Tests: test_denominators
   `test_a_qa_only_run_defaults_to_the_iterate_profile`, test_optimize
   `test_confirm_builds_run_the_iterate_profile_unless_a_term_reads_motion`.

## 8. The QA's drawing on a GPU (round 1 measurements)

(filled in from the round's measurements: docs/workstreams/incremental.md)
