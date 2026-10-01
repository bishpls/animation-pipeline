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

## State
- Deliverable 1 written and tested (charkit/tests/test_sweep.py: 8 tests, 49 s with the acceptance test).
- Next: commit, pregate, gate deliverable 1; then 2 (check families), 3 (review page: charkit/reviewpage.py drafted,
  `review page` wired in review.py), 4 (CODEMAP).
- Throwaway worktree for the w4 reproduction: the scratchpad's pr_beb14922 (git worktree, detached at beb14922): remove
  with `git worktree remove --force` when done.
