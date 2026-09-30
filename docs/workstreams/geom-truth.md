# geom-truth: one implementation of the geometry (tool/geom-truth)

Worktree `~/animation-pipeline-geomtruth`, branch `tool/geom-truth` from pipeline-3d 9397578. Approved by Michael.

**Goal.** Geometry is computed once, in the venv (charkit.geom and the builders), and saved as arrays; Blender only
instantiates meshes, materials, rigs and renders from them. The numpy evaluator (charkit.bodyeval) becomes the build's
own geometry step, exact by construction.

**This round:** inventory and drift per stage; the design (docs/GEOM_TRUTH.md); a pilot on the worst stage; the rollout
plan with owners. Don't change shapes: only where computation runs. Active workstreams on the same files: tool/skirt,
tool/garments2 (garments.py), tool/face (code_base.py), tool/hair3 (hair).

## Log
- 2026-09-30: worktree made; tool/infra's `charkit evaldrift` isn't on tool/infra yet (0 commits past pipeline-3d),
  so the drift inventory uses a comparison of our own (to be folded into evaldrift when it lands).
- Before builds (clean 9397578) come from a second worktree, `~/animation-pipeline-geomtruth-base` (branch
  tmp/geomtruth-base), so a sync of this worktree's edits can't reach them. A box build synced from here at 03:45 took
  the pilot code in; it's kept as `charkit/out/pilot0_mh` (a smoke test), not a before build.
- The drift comparison was `charkit/stagedrift.py` at first; it's now folded into tool/infra's evaldrift
  (`python -m charkit evaldrift [SPEC] --stages`, below).

## Pilot design (garments)
- `garments.build` talks to Blender only through a seam: `garments._object`, `_toon`, `_toon_tex`, `mask_skin`,
  `eyetex.to_blender_image`, `shade.outline`, and `ob.modifiers.new(...)` with its settings and custom properties.
  `charkit/geomstage.py` records build() venv-side with the seam replaced, saves the events and arrays
  (`OUT/geom/garments.npz`), and replays them in Blender through the real functions, in order. The builders' code and
  build()'s dispatch are untouched; the only edit to garments.py is `mask_skin` (build()'s last 7 lines, moved into a
  function, so the skin mask is one recorded call).
- The evaluator (bodyeval.garment_piece) records build() per piece the same way: its second dispatch, its tones table
  (garment_tones) and its thickness table (SOLID) are gone. Tones come from the recorded materials; textures are
  sampled as Blender's byte image holds them.
- The build: `cli.garments_geom` (a cached file_step after pieces_hair) writes the product and points the resolved
  spec at it (`garments_geom`); `scene.stage_garments` replays it. `CHARKIT_GARMENTS=blender` keeps the old path.
- The product keeps the body it was built on (float32); the Blender stage notes how far its own assembly is from it
  (trace note `garments_body`): the character stage's drift, measured on every build until it too moves venv-side.
- The venv assembly: `geomstage.assemble` (disk memo keyed by the spec minus the outfit, the code head/body files'
  content and the assembly's code closure). bodyeval.assemble_cached now uses it: its old key listed nine modules by
  hand and missed code_base, code_body and charkit.geom, so an evaluator could reuse a stale body.
- Coordinator (03:5x): tool/infra committed `charkit evaldrift` at c1016fa (not merged into pipeline-3d yet). It
  compares every shared check between the evaluator as the body fit reads it (bodyeval.resolve + bodyfit.BodyChecks)
  and a box build of the same commit, against a tolerance. **stagedrift is to be folded into evaldrift after infra
  merges** (e.g. `evaldrift --stages`, reusing its tolerance table and report); don't ship two drift commands. Before
  the gate: check `git log pipeline-3d` for the infra merge; if it's in, merge and fold now.
- pipeline-3d moved to e11fadb (tool/hair3 merged); nothing it touches overlaps this branch's files.
- The numpy versions differ: Blender 4.x bundles numpy 2.3.4 (Python 3.13), the venv has 2.5.3 (Python 3.14). The
  pilot's first mh build (pilot0_mh) shows the character assembly differing on 18 of 13,380 body vertices at float32
  (sub-micron): the same code, different numpy. It stays in every build's trace (`garments_body`, now in nanometres).

## Inventory (stagedrift on clean before builds, box, 9397578; details in docs/GEOM_TRUTH.md)
Box, the old evaluator on each build's own spec (`charkit-base: charkit/out/gt_before_{clawd,mh}/stagedrift/drift.md`):
- fit_cranium equal (1.1, clamped); assembly f32-identical (clawd) / 18 of 13,380 vertices differ in f32 (mh: numpy
  2.3.4 vs 2.5.3); eye and mouth parts 7e-7 L (Blender's float32 armature at rest).
- **hair: the evaluator doesn't model mode 'pieces'** (analytic locks instead): silhouette IoU 0.78 / 0.67 / 0.78.
  **accessories: no overlap** (the evaluator kept the buns the pieces carry; its carried filter lacked 'pieces').
- garments raw f32-identical (all 18 on clawd; mh: 12 shell vertices on the body's 18), mask identical; evaluated
  within 4e-5 L except the hull puff sleeves 0.008 L (bodyeval.solidify's shell on the wrong side).
- checks: 55 / 45 of 106 differ; hair_length up to 0.27 L, iou_hair up to 0.18, top 0.066; sheet_*_chin 0.025 (the
  measure's anchor in bodymeasure, not geometry). **Every hem check agrees.**
- laptop evaluator against the box build (cross-machine): raw garments f32-identical except the collar (133 vertices,
  4.8e-7 L); the code head's assembly differs up to 0.0027 L on 1,726 vertices (ARM against x86).

So the hems don't drift on this commit; the worst stage is the hair. The pilot covers both: the garments made one
implementation (they agreed only by coincidence), and the evaluator reads the hair pieces the build makes.

## Pilot, second half: the hair pieces in the evaluator
- `bodyeval.Evaluator.hair_parts`, mode 'pieces': the pieces from the build's product (`shape['pieces']`), else from
  the build's own step (`cli.pieces_hair`, cached) into charkit/out/bodyeval/pieces/KEY; carried in the head frame for
  body knobs as the geom mode is (exact_geom for per-spec). The carried filter now includes 'pieces', as
  scene.stage_hair's does.
- Laptop, the pilot evaluator on gt_before_clawd: hair f32-identical (all 9 pieces), silhouette IoU 1.0; the QA target
  identical; accessories 7e-7 L; checks differing 55 -> 30 (left: arms INFO, sheet chin anchor 0.025, sleeves
  0.008-0.01 (the solidify port), palette_iris_shade 0.05, iou_orange 0.003).

## Pilot result (box; before = 9397578 base worktree, after = 00f527c; both with --no-blend, after with --cache refresh)
- boarddiff before -> after: clawd 16 QA images identical, 294 checks identical; clawd_mh 16 identical, 292 identical.
- stagedrift after (the new evaluator on each build's own spec): checks differing 55 -> 29 (clawd), 45 -> 8 (mh).
  Garments f32-identical on every piece of both specs (mh's top and shorts too, now by construction); hair pieces
  f32-identical, silhouette IoU 1.0; accessories 7e-7 L; QA target identical.
- `garments_body`: clawd 0 nm (all 18,478 f32-equal); mh 18 of 13,380 differ (the numpy versions).
- Blender garments stage 11.5 s -> 5.7 s (clawd). The venv step: 10.6 s of garments plus an uncached assembly (81 s
  on the box for the code head; a same-copy rebuild hits the memo).
- Also found: bodyeval.recalc_normals (the bmesh port) winds the hull puff sleeves opposite to Blender (0 of 1,856
  polygons agree; every other piece 100%): the evaluated sleeves' 0.008 L (rollout step 7).
- Merged pipeline-3d 120d197 (hair3, hull-limbs) in at 6ec0c33; suite passes. Gates launched on 851fd15.

## For the other workstreams (coordinate here; the integrator folds it into the handoff)
- **tool/garments2, tool/skirt:** keep editing `garments.py` as you do. build()'s Blender calls must go through the
  seam (`_object`, `_toon`, `_toon_tex`, `eyetex.to_blender_image`, `shade.outline`, `mask_skin`, `ob.modifiers.new`
  with settings, `ob[key] = value`); anything else fails the build's venv step with SeamError naming it. Your template
  cuff and puff sleeve already fit. At merge, drop your hunks in `bodyeval.garment_piece` / `garment_tones`: they're
  gone here, and the recording covers every kind build() makes. Check a change with
  `python charkit/tests/test_geomstage.py` and `python -m charkit stagedrift BUILD`.
- **tool/hair3:** nothing to do; the evaluator now reads your pieces product (or runs `cli.pieces_hair` for a spec
  without one). Rollout step 2 (the hair volume, target and accessories venv-side, second after the pilot) is yours with tool/accessories.
- **tool/face:** nothing now. Rollout step 4 (the character product) splits `character.py`, not `code_base.py`; it
  waits for your jaw round. The cross-machine assembly difference (laptop vs box, up to 0.0027 L on 1,726 vertices of
  the code head) is worth a determinism pass in `code_base.wrap` some time.
- **tool/infra:** fold `charkit/stagedrift.py` into `evaldrift --stages` when you merge (or I do, if this branch
  merges after yours).
- The evaluator on a raw spec with no products (clawd_mh.json, laptop): the pieces made by the build's own step into
  charkit/out/bodyeval/pieces/KEY (first run 174 s, including a hull and hair-layers rebuild after the merge); then a
  body knob 2.7 s (composed), a garment knob 0.7 s (one piece re-recorded).
- **Gates of 851fd15 into 120d197:** default **WARN**, only on "the build takes 1.8x the CPU time" (1,226 -> 2,189 s):
  no check changed, all tests ok, garments stage 12.05 -> 5.74 s. clawd_mh **PASS** (no check changed; CPU 325 -> 455 s).
  The CPU is the garments step's own assembly (the code head's assembly is multithreaded LAPACK: ~80 s wall, most of
  the ~960 s CPU). Fix: the pieces step (parts.Case.load) and the garments step share one assembly memo, keyed on the
  spec sections the assembly reads (measured with charkit.cache's tracked dicts, guarded by a test).
  ("stage hair: knobs hair changed" in both reports is the pieces path, which names the build's own folder.)

- Coordinator (later): tool/infra merged into pipeline-3d (cfcdc3a). Merged here at 80c5944. **stagedrift is folded
  into evaldrift**: `python -m charkit evaldrift [SPEC] --stages` (or `--build DIR --here --stages`) adds the per-stage
  geometry comparison (evaldrift.stages, stage_drift, GEOM_TOL, a `## stages` section in drift.md; exit 1 on stage drift
  too). `charkit/stagedrift.py` and the `stagedrift` command are gone. Its own check comparison is dropped in favour of
  evaldrift's (the evaluator as the body fit reads it).
- Rollout reordered at the coordinator's request: the rest of the hair stage (volume, target, accessories) is step 2.
  evaldrift's first result on clawd.json showed the same thing: the hems agree, the evaluator has no cut-piece hair
  (fixed on this branch), and sheet_face lacks the eye-line registration (0.025 L; tool/face has it; step 8).
- Gates of 83cadf4 (the shared memo) were launched into pipeline-3d before the infra merge; the final gates are rerun
  on the branch head after it.
