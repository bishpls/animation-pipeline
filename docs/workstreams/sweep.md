# Deterministic tooling: sweep, check families, review pages, the code map (tool/sweep, 2026-09-30)

Worktree `~/animation-pipeline-sweep`, branch `tool/sweep` from pipeline-3d 342e88c.

Why (Michael, 2026-09-30): replace repeated agent hand-coding with deterministic tools. The audit of 69 rounds
(`~/animation-pipeline-3d/charkit/out/audit/20260930/`): variant harnesses and their runs are the largest category (up to
7.4 h, 22% of active agent time, in 60 of 69 rounds); 72% of the harnesses import charkit in-process, 3% launch builds,
52% loop over a literal parameter list, 5% resemble one another. So one parametrised tool, not a script library.

Deliverables, each gated as its own small merge:
1. `charkit sweep`: in-process, stage-level variant runner; swap mode (attribution). Acceptance: reproduce two
   historical sweeps' numbers exactly (pieceref's w4; hair5's terminator swap), tests, usage in the module docstring.
2. Declarative check families with one generic `charkit calibrate` path; two hand-written checks ported, identical
   values.
3. `charkit review page`: the standard review page generator.
4. `docs/CODEMAP.md`, generated from docstrings and public functions.

Rules: don't touch the hair, face, garment or hands builders. Tooling moves no check.

## 1. `charkit sweep` (charkit/sweep.py; usage in its docstring)

What it is: a declaration (base build, stage, rows) -> every row rebuilt in-process at its stage, spliced into the base
bundle, measured by the QA's own parts (registry order, qa.json's names, authority grading) -> OUT/sweep.json,
OUT/sweep.md, OUT/ROW/res.json (+ board.png).
- Stages: `qa` (nothing rebuilt; rows patch module attributes, `qa:MODULE.NAME`), `garments` (one bodyeval.Evaluator;
  garment and accessory objects spliced: the bow harnesses' splice), `hair` (cli.pieces_hair, the build's own
  file_step, on the row's spec; pieces spliced with their shading normals: labart.py's splice; `style.hair_pieces.KEY`
  rows run it uncached with the style patched).
- Rows: `set` (shared), `variants`, `grid` (every combination), `oat` (one path at a time); a `control` row first (the
  base spec through the same stage): deltas against it, so the evaluator's drift from Blender cancels.
- Spliced objects: declared, or those any row's rebuild changed against the control (one set for every row; with
  --jobs, a shard that spliced another set reruns with the union).
- Always measured beside the chosen checks: sheet_pieces and hair_pieces (every piece's shape IoU per view); the shape
  table lists every piece/view that moved; the guard flags a row that improves a check while a piece's IoU drops > 15%.
- Every row is drawn with the numpy drawing (B.path None): the render drawing draws the build's export by object name,
  so it would not see a spliced or swapped object (qarender.view matches by name only). Verified harmless for
  art_terminator_hair (render and numpy read 3.262 on the swap), but other render-drawn checks would be wrong.
- A base without geom/ (a preview): its head and body codes remade by cli.code_head / code_body (file steps).
- `--jobs N`: N processes, each in a machine build slot (procs.acquire_slot); the laptop has 1 slot.
- `--box [NAME]`: `remote run --fetch OUT` (the base must be a build on the box).
- `--code ROOT`: the sweep with another tree's charkit (runs sweep.py by path with ROOT first on sys.path).
- Swap mode: `sweep swap A B --check C [--drop] [--objects PAT] [--inputs PATH[=V]]`: A, B, A + B.x, B + A.x (and A - x,
  B - x with --drop) on the check's part; the share of the A -> B move each swap carries; every object's move between
  the builds (pairmove's: max vertex move, Kabsch rotation); --inputs rebuilds B with A's input at a stage (hairswap's).
- Caveat (documented): a `qa:` patch reaches what reads the attribute at call time; a default argument bound at import
  (pieceqa.spikes(min_depth=SPIKE_MIN)) keeps its value.

### Acceptance (reproductions; `charkit/out/sweep/acceptance/`, compare.py there)
- **pieceref w4** (tool/pieceref var.py w4, 2026-09-30 20:32 at pieceref beb14922): `sweep run pieceref_w4.json --code
  <a detached worktree of beb14922>` (stage garments, base bow2's b2_close, spec charkit/spec/clawd.json resolved,
  objects [bow], parts sheet_pieces, bow_profile, bow_parts, iso_pieces, collar_flags, rebase false: var.py read the box
  build's paths as written). **59 checks compared, 0 differences** (value, views, iou, ours, design, status) against
  `~/animation-pipeline-pieceref/charkit/out/pieceref/harness/w4/res.json` (its sheet_body was added later by qaonly.py
  at other code: not compared). One Evaluator for the sweep (var.py made one per variant): identical.
- **hair5 terminator swap** (tools/hair5/term.py, term_A.json / term_base.json: A = h5_base 1.804, B = hair5_b 2.575):
  `sweep swap h5_base hair5_b --check art_terminator_hair --objects hair_ahoge,hair_flyaways,hair_upper_back,
  hair_lower_back --drop`: **10 rows compared, 0 differences** (worst ratio and every per-view ratio): B - hair_ahoge
  1.900, A + B.hair_ahoge 3.262, B + A.hair_ahoge 1.899, B + A.hair_flyaways 2.969, B + A.hair_upper_back 2.761,
  B + A.hair_lower_back 2.666, A + B.hair_upper_back 1.804, A + B.hair_lower_back 1.878. 14 rows in 120 s (8 s a row).
  Also a test (test_reproduces_hair5_terminator_swap; skipped where the builds aren't).
- Functional runs: garments stage with control on hair4's hair5_b3 (`garments_demo`: bow ribbon turn 30 / 50; control
  66 s with the evaluator's context, then 5 s a row; boards cropped to the bow), hair stage (`hair_demo`: pieces_opts.gap
  0.004; 50 s a row, the pieces step), qa stage with --jobs 2 (`jobs_demo`).

## 2. Declared checks with generic calibration (charkit/declared.py; docs/CHARKIT.md "Declaring a check")

- Families (one function each, on pieceqa's primitives): shape_iou (as qa3d.sheet_pieces measures: bodymeasure.
  piece_shapes, iou_tol by default, exactly piece_<id>'s per-view values: bow front 0.8962, profile 0.3459 on
  hair5_b3; or close=True, collar_back_iou's closed-mask IoU), width (ratio or rms of tenths), edge (top/bottom),
  tips (pieceqa.spikes on the silhouette; graded the worse of depth and count), angle (PCA axis), ink_between (two
  pieces' boundary with no ink: ours from the outline hulls drawn on the design's grid, our_lines; the design's masks
  less its line class), position (centroid). `fold`: the drawn pieces we don't build folded in (the bow's tails).
- A declaration is a literal DECLARED_CHECKS in any charkit module (ast-read, no central list); `part` 'declared' (the
  generic part, order 1790; nothing declared: nothing measured) or a part that evaluates its own (evaluate_part);
  limits a list or a reference to a part's table ('charkit.pieceqa.LIMITS.rows'); `flag`; `note`; `calibrate`.
- Generic calibration: calibrate.entries() adds each declaration's `calibrate` block as an entry (after calib/*.py's own,
  which keep priority), the adapter chosen by the part (declared.ADAPTERS: Declared for 'declared', a subclass of
  calib.details.Details whose our_lines is the drawing's ink moved with the labels, none for a floor).
  `calibrate CHECK --declared draft.json` (or CHARKIT_DECLARED) measures and calibrates a draft before it's committed.
- **Port:** piece_details' shorts_{view}_hem (edge family) and shorts_{front,back}_width (width family) are now
  declarations in pieceqa.py (waist() keeps the waistband). **Identity: 413 checks (all of piece_details) on 7 builds
  (body6_render and co_render known-bads, hair5_b3, h5_base, b2_close, preview 342e88c, hair5_1580f95), 0 differences**
  against 342e88c's pieceqa (`charkit/out/sweep/families/port_identity.py`), and a synthetic test with the old code
  kept verbatim (test_port_identity, 12 random trials).
- **Generic calibration = the hand adapter's:** the six shorts checks declared again in the generic 'declared' part
  from a JSON draft (`charkit/out/sweep/families/draft_shorts.json`, no adapter code), calibrated on cur_8b5ecae with
  known-bad body6_render: design moves, known-bad, floors, current and verdict **identical (30 fields, 0 differences)**
  to the hand path (Details adapter, piece_details) and to the committed records (5 calibrated, shorts_front_width
  blind as recorded). (body6_render is linked into charkit/out/calib/builds from ~/animation-pipeline-infra3's store.)

## 3. `charkit review page` (charkit/reviewpage.py)

`python -m charkit review page PAGE.json [--out DIR] [--open]`: title, summary {recommended, asked, numbers}, builds
[{label, path}], views, regions, checks, sweep, notes -> DIR/index.html and DIR/img (default
charkit/out/review_pages/<slug>). Order: the summary box (Recommended, Asked of Michael, Key numbers: given, or the
first named checks across the builds), per view the design beside each build (full figures at 560 px, heads at
300 px/L), close-ups by region (REGIONS: face, hair, bow, hands, cut in L round the eye line as the all-in page did,
one row per view at one height: a column's scale is the next's), a sweep's table and boards, the numbers (qa.json, flag
checks [F]). Build folders are only read: a preview's page crops when present, else cut from its boards as
charkit.preview does, else drawn from its bundle. Demo: `charkit/out/sweep/review_demo/` (the 342e88c preview, hair5_b3,
h5_base, the garments demo sweep), 8 s.

## 4. The code map (docs/CODEMAP.md, charkit/codemap.py)

`python -m charkit.codemap` (ast only, under a second; `--check` says whether the file is current; no test enforces
freshness, so a stale map never blocks a gate). A curated header (where the build, builders, evaluators, QA parts,
calibration, sweep, gate, review pages, sim, renderer and geometry kernel live), then generated: the QA parts by
registry order (part, check prefix, table, function), the commands (cli.main's dispatch), the calibration entries,
the declared checks, and every module under charkit/, geom/, render/, sim/, calib/, steps/, boards/, styles/ with its
docstring's opening and each public function's signature and first docstring sentence. 3559 lines.

## Gates
- Gate 1 (deliverable 1, sweep): **tool/sweep 1381b4f into pipeline-3d 961037c: PASS under K**; nothing blocks, 0 items
  reported (no check moved); the candidate built (cli.py changed: its venv steps' keys missed, CPU 737 -> 940 s,
  1.28x); 78 test files ok. Report `charkit/out/gate/gate_tool-sweep_1381b4f_into_961037c.md`. Pregate PASS (0 moved).

## State (round end, 2026-09-30 ~23:00)
- All four pieces done, committed and gated:
  - Gate 1, deliverable 1 (sweep): tool/sweep 1381b4f into 961037c: **PASS under K**, 0 items, CPU 1.28x, 78 tests ok.
  - Gate 2, deliverable 2 alone (tmp/sweep-declared = 49d073b) into 961037c: **PASS under K**; 1 item reported, not
    blocking: piece_details' measuring code changed with no registered step, **0 checks moved** (same geometry; the
    port is identical); CPU 762.8 s against 737.1 (1.03x). Report charkit/out/gate/gate_tmp-sweep-declared_49d073b_
    into_961037c.md.
  - Gate 3, deliverables 2-4 (tool/sweep a3a7f2a) into 961037c: **PASS under K**, the same one reported item, 0
    checks moved, CPU 762.1 s (1.03x), 81 test files ok. Report charkit/out/gate/gate_tool-sweep_a3a7f2a_into_961037c.md.
  - 20ef2a7 (docstrings, codemap without line counts, notes) and this notes commit came after: no build reads them
    (sweep.py, codemap.py, CODEMAP.md, docs); test_sweep and test_codemap pass locally. Carry or a tests-only re-gate.
- tmp/sweep-declared deleted after its gate; the w4 reproduction's throwaway worktree removed.
- Functional runs at round end: `--box --jobs 2` on bow2's b2_close (box path, 348 s, fetched to
  charkit/out/sweep/box_demo): its guard flagged turn=50 (bow_profile_ribbon improves while piece_bow profile 0.543 ->
  0.352, -35%): the bow-ribbon gaming pattern, caught by the tool. `swap --inputs hair.shape.pieces_opts --stage hair`
  on h5_base/hair5_b (charkit/out/sweep/acceptance/swap_inputs): runs end to end; its hair-stage control reproduces
  hair5_b's own art_terminator_hair 2.575.

## Next steps
1. The coordinator merges tool/sweep (tip) or 1381b4f / 49d073b as wanted; nothing running.
2. Possible follow-ups (coordinator's call): port more hand checks to declarations (collarqa's are other branches'
   ground: coordinate); the gate's guard reading declared shape_iou checks; a sweep stage for the face (code_head);
   `sweep --box` uploading a local base.

## What other agents should switch to
- variant harnesses (var.py, sweep.py, batch.sh, lab.py) -> `python -m charkit sweep` (garments / hair / qa stage);
- attribution scripts (termlab.py, term.py, labart.py, pairmove.py, hairswap.py) -> `charkit sweep swap A B --check C
  [--drop] [--inputs PATH]`;
- calibration adapters for a new flag -> a DECLARED_CHECKS declaration + `charkit calibrate CHECK [--declared F.json]`;
- per-round page scripts (make.py) -> `charkit review page PAGE.json --open`;
- code reading -> docs/CODEMAP.md (`python -m charkit.codemap` to regenerate).
