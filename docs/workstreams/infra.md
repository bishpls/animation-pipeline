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

## Verification

(filled in below as the runs land)

## Open items

- The hook isn't installed in the pipeline-3d worktree (the integrator's call).
- A bundle schema bump would disable the 2×2 (WARN, unverified). The fix then is exporting the candidate's scene with
  the baseline's `bundle.py`.
