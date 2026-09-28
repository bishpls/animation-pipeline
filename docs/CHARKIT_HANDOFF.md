# charkit toolkit: handoff (2026-09-28)

This is where a new session picks up. It covers the goal, what's merged, what's in flight, and the next steps in order.
It also records the decisions and rules to keep. The build flow, each check and each tool are in `docs/CHARKIT.md`.

## The goal, and where we are

charkit builds anime 3D characters (HoYoverse-level target) in code. The test character is Clawd (`charkit/spec/clawd.json`).

Michael **paused the Clawd buildout** to invest in the toolkit: measurement, observability and control first. Then a
**checkpoint review** with him, then a secondary phase. Nothing in this round is pushed. Everything is committed on
`pipeline-3d`, and `main` is fast-forwarded to it:

- `~/animation-pipeline` is the main checkout (`main`), shared with other sessions.
- `~/animation-pipeline-3d` is the integration worktree (`pipeline-3d`). Merge branches here, and fast-forward `main` with
  `git -C ~/animation-pipeline merge --ff-only pipeline-3d`.
- Head at handoff: `eaf0ec8`.

The plan doc "Charkit Toolkit Buildout Plan" is a Claude Doc on Michael's first account. A new account may not see it,
so this file restates what's needed from it.

## Merged this round (on pipeline-3d / main)

| Area | What | Where |
|---|---|---|
| Observability | Build trace: per-stage state log, geometry hashes, mesh health, landmarks, timings; `charkit trace A [B]` diffs two builds | `charkit/trace.py` |
| Measured QA | Graded checks with overlays in `qa/qa.json`: shape and ref IoU, scalp, poke-through, hair noise | `charkit/qa3d.py` |
| | Face shape vs the TRELLIS target | `faceqa.py` |
| | Eyes vs the rig's eye layers | `eyeqa.py` |
| | Face vs the design's model sheet (front, 3/4, profile) | `sheetqa.py` |
| | Full body in 4 views | `bodyqa.py` |
| | Expressions vs the sheet's heads | `exprqa.py` |
| | Palette (CIEDE2000) | `paletteqa.py` |
| | Face folds | `qa3d` |
| Mesh kernel | Repair, booleans, volumes, SDF, remesh, raster, BVH; `--hair geom` makes the generated hair one closed shell | `charkit/geom/` (see `docs/GEOM.md`) |
| TRELLIS.2 fork | Field export, multi-view conditioning, part labels, per-part surfaces | `tools/imageto3d/trellis_ext/` |
| Anime base mesh | `--base anime` or `spec.base`: clean topology, folds 1014 → 135 | `charkit/base_anime.py` |
| Export / runtime | Our glTF/VRM writer with the `OPENADS_charkit_look` extension; WebGPU look renderer matches Blender to under 1/255; inspector with QA and trace panels | `charkit/gltf.py`, `engine/three/charkit/`, `projects/charkit-look` |
| Fitting | Fast face evaluator, generic fitter, face fit; knobs `nose_tip`, `low_flat` | `faceeval.py`, `fitkit.py`, `facefit.py` (`charkit fit`) |
| | The fitted knobs are already in `clawd.json` | |
| Tune loop | Fitters, then checkpoints (full build plus QA, accept only if nothing regresses), probe, triage into work items, review notes → tickets | `tune.py`, `triage.py` (`charkit tune / triage / review`) |
| Outfit graph | 26 pieces with attachments, layers, extents and motion classes (rigid, spring, cloth); `garments.panel` template | `outfit.py`, `charkit/refs/clawd/outfit_graph.json` |
| Speed | Stage and QA cache keyed on recorded reads (warm rebuild 4.6 s); persistent Blender worker | `cache.py`, `worker.py` |
| References | One manifest per character: roles, scale, provenance, cautions, and which reference is authority per measure | `charkit/refs/clawd/manifest.json`, `manifest.py`, `charkit refs-check` |
| Process | Merge gate: throwaway sparse worktree, tests, build, QA diff and trace diff | `charkit gate BRANCH` |
| | QA history | `charkit history NAME` |
| | Build process records | `charkit ps / kill / wait` |
| | Machine-wide build slots and a memory check | `charkit slots N` |
| | Sparse worktrees | `tools/worktree.sh` |

## In flight at handoff

1. **`tool/bodyfit`** (`~/animation-pipeline-bodyfit`, head `d7f4ea7`), wrapped up and committed, **not merged or
   gated**. Read its `docs/BODYFIT_STATUS.md` first. What it has:
   - a fast numpy body, garment and hair evaluator: about 90x Blender, geometry within 4e-7 m, all 93 sheet checks
     grading as Blender does;
   - `bodysens`;
   - per-piece fitting against the sheet, with rest-pose knobs;
   - registration as the tune loop's body fitter.

   Its fitted Clawd builds with 27 checks better and none worse:

   | Check | Before | After |
   |---|---|---|
   | shape_iou | 0.588 | 0.741 |
   | ref_iou | 0.549 | 0.660 |
   | body checks passing | 10 of 49 | 20 of 49 |
   | palette checks passing | 5 of 13 | 11 of 13 |
   | face and eye checks | | unchanged |

   It holds the head's size fixed while fitting the body. So Clawd became 1.468 m and 5.87 heads, from 1.55 m and 6.2
   heads; `--free-head` restores the old behaviour. **That is a design change to show Michael at the review.**

   To resume:
   1. merge `pipeline-3d` (conflicts are likely in `cli.py` and `docs/CHARKIT.md`; keep both sides);
   2. run the tests;
   3. run `python -m charkit gate tool/bodyfit --into pipeline-3d`;
   4. refresh `bodysens` (about 30 min; the current table predates a Solidify fix);
   5. merge.

   Known gaps:
   - the buns sit lower and the hair is about 12% narrow, and no knob reaches either (the TRELLIS hair carries them);
   - the skirt's front opening;
   - the IoU and leg checks trade against each other;
   - two single-pixel checks flip easily.
2. **`tool/measure`** (`~/animation-pipeline-measure`, head `bc816d0`), **ready but parked on purpose.** It moves all
   measurement out of Blender:
   - Blender exports one geometry bundle per build (`charkit/bundle.py`, `OUT/bundle/`);
   - every QA check runs in the venv on the numba rasteriser; QA takes 8–13 s instead of 83–98 s, and Blender's peak
     memory drops by about 0.5 GB;
   - `faceeval` calls the QA's own functions (46 of 46 checks match);
   - 92 check values shifted slightly and six statuses changed. All are registered as remeasurements in
     `history.STEPS`.

   Its gate passed against `6419bcd`. It must be gated against the **baseline build test** (step 2 below), then merged.
   `bodyeval` should then move onto `bundle.Builder` and `qa3d.evaluate(...)`; its own measure code is duplicated.

## End-to-end run at handoff (2026-09-28, the merged stack without bodyfit)

`charkit tune charkit/spec/clawd.json --out charkit/out/e2e --budget 8 --review --workers 3` ran unattended in 549 s.
The steps, in order:
1. ck0 start: cached, 4 s. Score 114.62; 43 pass, 30 warn, 41 fail.
2. ck1 geom hair: **accepted**. Score 113.10.
3. ck2 anime base: **rejected** (eye width and iris ratio, the laugh mouth, neck-to-jaw).
4. The face probe found the face converged, so the refit was skipped.
5. ck3 final: stop, converged. Score 113.10; 43 pass, 31 warn, 40 fail.

Then the final spec was built with `--vrm`: `charkit/out/e2e/export/clawd.vrm` passes the Khronos validator with 0 errors
and 0 warnings. Triage produced 73 work items in `charkit/out/e2e/work_items.md`:
- needs a knob: 45, mostly body and garments, which bodyfit addresses;
- needs a capability: 9;
- trade-off: 8;
- measurement uncertain: 6;
- knob at a bound: 3;
- needs a measurement: 2.

After bodyfit merges, rerun this exact command as the baseline for gating `tool/measure`.

## Next steps, in order (the checkpoint)

1. **Merge `tool/bodyfit`** through the gate.
2. **Baseline full build test** on the merged stack:
   `python -m charkit tune charkit/spec/clawd.json --review`. Then check the VRM export (`charkit build ... --vrm`, and
   `node tools/gltf_validate.mjs`) and the inspector (`node engine/render.mjs projects/charkit-look --serve`). Keep this
   run's `work_items.md` as the baseline.
3. **Gate and merge `tool/measure`** against that baseline, then run one confirming `charkit tune`.
4. **Clean up the merged worktrees:** fit, speed, tune, bodyfit and measure, once merged.
   - Archive the valuable outputs (gate reports, before/after sheets, fit reports) into
     `~/animation-pipeline-3d/charkit/out/archive/<name>/`. Earlier ones are already there.
   - Check `git status` for uncommitted work, then `git worktree remove` and `git branch -d`.
   - Never use `--slim` or `git sparse-checkout set` by hand in zsh: an unquoted `$var` is a single word there, and git
     deletes ignored-only directories outside the cone. `tools/worktree.sh --slim` now guards against this.
5. **Checkpoint review with Michael.** Make a private review page: the design sheet next to ours per view (front, 3/4,
   profile, back, face close-ups, eyes, expressions), before and after this round, the QA summary, and these open
   decisions:
   - **Anime base:** it cuts face folds from 1321 to 320, but regresses eye width and iris ratio, the laugh mouth, and
     neck-to-jaw. Is it worth making the default after fixing its eye rings?
   - **Eye aspect:** still FAIL (0.74 of the design's tall oval). It trades against pupil run and lid gap.
   - **Framing:** `scene.cull_face` removes the cheek side locks when the jaw widens. Keep the locks in front of the
     cheeks, as geom hair does. `face_shape_coverage_*` against TRELLIS is INFO now: the sheet is the authority for
     framing.
   - **"The face reads long" ticket:** it now measures 6% short. Does it look short to him? If not, the measurement is
     wrong.
   - The top triaged work items from the tune run.
6. **Secondary phase**, only after that review:
   1. **Remote build backend (scoping) comes first:** a CPU spot VM for parallel builds, the existing L4 box for EEVEE
      renders, `charkit build --remote`, platform-keyed gate baselines, the same guardrails as the GPU box. New cloud
      resources only with Michael's go-ahead.
   2. **Motion QA:** range-of-motion and dance-clip sweeps. Measure interpenetration, stretch, joint volume and spring
      stability.
   3. **A generic path for untemplated parts:** the cleaned generated surface plus auto-rigging.
   4. **Spring bones:** VRMC_springBone export and runtime simulation, driven by the outfit graph's motion classes.
   5. **Generated-view consistency** for single-image input.
   6. **Hair as components:** ponytails, twintails, buns and locks, each rigged with its own physics.

## Known issues and work items

- **Tune triage (73 items):** 45 need body-fitter knobs; 9 need a capability (hair noise, framing/cull, fold-free
  expression shapes, poke-through, eye-highlight side); 9 are trade-offs; 2 have a knob at its bound (the nose tip is
  capped at 0.04 L); 6 are within measurement error. Re-run `charkit triage` after the baseline test.
- **Face folds:** 1321, from the laugh, yawn and wavy mouth keys; MakeHuman's mouth cavity doesn't follow tall openings.
- **Colour:** `i3d.load_glb` gamma-encodes TRELLIS colours twice. `geom.io.load` gives true colours. The skin classifier
  in `faceqa.SKIN` was calibrated on the double-encoded ones.
- **Cache gaps:** a `head.width` change rebuilds garments, correctly (the neck joints move); body knobs rebuild hair
  (float rounding). The mesh/geom hair-mode switch is fixed in `eaf0ec8`.
- **Face fitter:** refresh rounds aren't capped by `--budget`. The tune loop's probe skips fits that can't pay off.
- **Geom hair** keeps the generated side locks, so it shows less face than the design. `hair(face=True)` or the cull
  fix addresses this.

## Rules and decisions to keep (Michael's)

- **Publishing and licences:**
  - Never push or publish without asking. Commit messages end with
    `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`.
  - The repo is public: keep cloud project, VM and bucket names out of tracked files. The GPU box's config is
    `infra/gcp/gpu.env` (gitignored; there is a copy in `~/animation-pipeline-3d`). It's stopped; `infra/gcp/gpu.sh`
    manages it.
  - Licences are read for commercial use: no GPL or AGPL code or deps; no non-commercial models.
- **Secrets:** keys are in `.env` / `.env.local` in the main checkout; never print or commit them. The Hugging Face
  token lives only in the cloud secret manager.
- **Models:** image models are fine for references and keys. Video models are off. Log paid calls to
  `tools/ledger.jsonl`.
- **How to work:**
  - **Measure first:** build the measurement before iterating. When something is judged only by eye, add the check that
    would catch it.
  - **Own the toolstack:** when a tool fights you, ask whether to improve, fork or replace it. Be ambitious.
  - **Template libraries are additive:** a reference's items (expressions, pieces) become targets. Missing ones get
    added to the template; the input never limits the library.
  - **Authority per measure** is in the manifest: the model sheet for 2D shape, framing, silhouettes, expressions and
    palette; TRELLIS for face depth and hair shape; the rig for eyes.
  - **Human review at checkpoints** and for taste calls. Metrics are proxies; Michael's eye is the ground truth.
- **Machine:**
  - The Mac has 16 GB. One Clawd build peaks at 2.2 GB of Blender. Use `charkit slots 3` when the machine is dedicated
    to this, 2 otherwise.
  - Run at most about 3 agents at once.
  - Wait on long jobs with `run_in_background` and notifications, or `charkit wait OUT_DIR`, never a foreground `until`
    loop.
  - Create worktrees with `tools/worktree.sh` (sparse).
  - Disk: the other sessions' `~/games` holds several hundred GB; keep our outputs small.
- **Git and other sessions:** don't touch other sessions' uncommitted files in the main checkout (for example
  `tools/ledger.jsonl`), or the geno and melee worktrees and `~/games`.

## Handy commands (run from `~/animation-pipeline-3d` with `~/animation-pipeline/.venv/bin/python`)

```
python -m charkit build charkit/spec/clawd.json --out charkit/out/X --boards views --no-blend [--hair geom] [--base anime] [--vrm]
python -m charkit trace charkit/out/A/trace.jsonl [charkit/out/B/trace.jsonl]
python -m charkit gate BRANCH [--into pipeline-3d] [--args "--hair geom"]
python -m charkit tune charkit/spec/clawd.json [--review]   |   python -m charkit triage DIR   |   python -m charkit review serve BUILD
python -m charkit fit charkit/spec/clawd.json --out DIR      |   python -m charkit outfit charkit/spec/clawd.json
python -m charkit history clawd [--check CHECK]              |   python -m charkit ps / slots / wait OUT_DIR
python -m charkit refs-check charkit/spec/clawd.json         |   tools/worktree.sh NAME --profile charkit
for t in charkit/tests/test_*.py; do python $t; done        # the whole suite, about 26 s
```
