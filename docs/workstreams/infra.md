# Infrastructure workstream (tool/infra, 2026-09-30)

Michael's process decisions of 2026-09-30 (the handoff's "Process and architecture decisions"), items 2–5: an automatic
preview after every merge, self-registering QA parts and measurement steps, the anti-gaming 2×2 in the gate, and a
standing evaluator-against-box drift test. Worktree `~/animation-pipeline-infra`, branch `tool/infra` from
pipeline-3d 9397578.

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
- **The verdict.** A check that regresses under the old measure fails the gate unless `--accept PATTERN[,…]` names it
  (`remote gate` passes `--accept` through). If a crossed run can't run, the verdict is WARN (unverified).
- The report gets a 2×2 table.
- **The bundle format** is schema `charkit.bundle/1`, unchanged since tool/measure: named arrays plus JSON metadata,
  read by name. Old code reads a newer bundle unless an array it reads was renamed or removed, and such a part comes
  back SKIPPED, which shows. A schema bump would need the candidate exported by the baseline's bundle writer (open
  item).

## 4. The evaluator against the box: `python -m charkit evaldrift [SPEC]`

- It builds SPEC on the build box, then runs the evaluator there on the same synced copy: `bodyfit.BodyChecks(spec,
  graph).checks(spec, 'all', fine=True)`, which is the body fit's own view (shape_*, body_*, palette_*, sheet_*,
  piece_*).
- It compares every check both sides have. The tolerance is 0.01 by default (L, IoUs, shares) and 0.5 for palette_*
  (CIEDE2000); `--tol` sets one for all.
- It writes `drift.json` and `drift.md` into the build folder and exits 1 on drift. `test_evaldrift` tests the
  comparison.

## Verification

(filled in below as the runs land)

## Open items

- The hook isn't installed in the pipeline-3d worktree (the integrator's call).
- A bundle schema bump would disable the 2×2 (WARN, unverified). The fix then is exporting the candidate's scene with
  the baseline's `bundle.py`.
