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
- **Resumed 2026-09-28 on the second account:**
  - `tool/bodyfit` merged at `77721ff` (gate PASS);
  - the dance port committed at `885d53c`;
  - the baseline tune is running in `charkit/out/baseline`.

The plan doc "Charkit Toolkit Buildout Plan" is a Claude Doc on Michael's first account. A new account may not see it,
so this file restates what's needed from it. That includes the plan's character buildout (its phases 3 and 4), under
"Functionality buildout" below.

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

1. **`tool/bodyfit`: merged 2026-09-28 at `77721ff`.**
   - The gate passed: 27 checks better, none worse, all 17 test files ok, Blender time 113 → 114 s. The report is
     `charkit/out/gate/gate_tool-bodyfit_3c295b8_into_315045c.md`.
   - Still to do: refresh `bodysens` (step 4 below).

   It was at `~/animation-pipeline-bodyfit`, head `d7f4ea7`. Its `docs/BODYFIT_STATUS.md` is now on `pipeline-3d`.
   What it has:
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

   The merge steps, all done except the `bodysens` refresh:
   1. merge `pipeline-3d` (it merged cleanly, as `3c295b8`);
   2. run the tests;
   3. run `python -m charkit gate tool/bodyfit --into pipeline-3d`;
   4. refresh `bodysens`: still to do. It takes about 30 min, and the current table predates a Solidify fix. The tune
      doesn't read it, since the tune measures its own tables, so it doesn't block the baseline;
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

   **Expected conflict: `charkit/sheetqa.py` `measure_ours`** (a trial `git merge-tree` against bodyfit shows it).
   - measure calls `faceqa.zbuffer(..., thin=(CLASS['line'],))`, since its `zbuffer` gains `method` and `thin`;
   - bodyfit made `zbuffer` and `face_region` injectable, and passes `bodymeasure.zsplat`, which has no `thin`.

   The clean resolution is to use measure's rasteriser on both paths and retire `zsplat`. That is the bodyeval
   deduplication above.

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

## Michael's review of the end-to-end run (2026-09-28): read before prioritising

His verdict: a clear, significant improvement and a sound method, but still far from production-ready. **Get the face
truly right before the hair rework**: hair needs strands, chunks and layering eventually, but it comes later.

What he saw:
- **Face front:** much better; the old T-shaped face is gone.
- **Face profile:** depth and contour are still badly wrong. The profile reads as a flat mask plate with the eye on its
  front edge, a tiny nose bump, and a pale boxy patch of skin where the hair was cut. `sheet_profile` reports only
  ~0.04 L WARN, so **the metric understates it**.
- **Eyes:** shape much improved, but **the pupils still read too small**. The pupil-to-iris-to-sclera area ratios aren't
  measured.
- **Eyes through hair:** eyes are drawn over the side locks in profile, which is questionable.
- **Mouth expressions:** need a quality and detail pass.
- **Garments:**
  - the skirt is one stiff flared piece, where the design has zig-zag, stepped pleat panels;
  - the puff sleeves are off.
- **References:** `sheet_views` and `sheet_body` use the 3D-style key (made from the Live2D rig) as their reference
  column, not the model sheet `idol_D`. Mixed references across the suite add measurement noise.

What it means for the method (my read):
1. **Mixed references.** Graded checks compare against different references: `ref_iou` against the 3D-style key,
   `shape_iou` against TRELLIS, the sheet checks against idol_D, eyes against the rig. They pull fits in different
   directions.
   - Grade each concern only against its manifest authority. Make `ref_iou`, and `shape_iou` outside TRELLIS's
     authority (depth and hair), INFO.
   - Rebuild the review sheets from the model sheet's own figures, matched per view and scale.
2. **Position-average metrics miss shape.**
   - Profile: use feature-level measures instead of a mean gap. That means nose-tip projection, nasion depth, lip and
     chin projection, the jaw angle, the forehead slope, **how far the eye sits back from the brow-nose line** (anime
     profiles set the eye well behind it; ours sits on the front edge), slope and curvature along the profile, and the
     worst deviation, not only the mean.
   - Eyes: grade the area ratios (pupil to iris, iris to opening, visible sclera).
   - Garments: shape per piece, using the outfit graph's per-view piece masks. That covers puff roundness and volume,
     and the pleat zig-zag.
3. **No perceptual weighting.** A 0.04 L profile error looks "catastrophic" while a 0.04 L skirt error looks mild.
   Calibrate the weights and limits from review: when Michael calls something severe and the check says WARN, tighten
   that check. Consider a learned perceptual similarity per view and region (DINOv3 features, already licensed for the
   TRELLIS work) as a complement, calibrated against his judgements.
4. **Resolution.** idol_D gives about 115 px per head length, so the nose and mouth are only 3–5 px. Higher-resolution
   authority views of the head are needed (profile and 3/4; the rig covers only the front). Options are an artist
   drawing, or image-model views derived from the sheet and checked against it; paid image calls need Michael's
   go-ahead.
5. **Capability, not just knobs.** The profile needs a head-shaping capability: fit the midline profile spline directly
   to the design's profile, set the eye's depth, and give the nose, lips and chin real structure. The `nose_tip` knob is
   capped at 0.04 L.
6. **Features through hair:** limit it to fringe objects, and fade it with view angle. Measure it against whether the
   design shows the eye in that view.
7. **Better review input:** notes anchored to a region and view (click on the board), with a severity score, so a note
   maps to a measurement and calibrates it.

Suggested priority, face first:
1. reference consistency (items 1 and 7);
2. profile feature metrics, a high-resolution profile reference, then the profile head-shaping capability;
3. eye area ratios and pupil size;
4. review calibration and a perceptual metric;
5. a mouth detail pass;
6. garment pieces (puffs, pleated panels);
7. hair components and rework later.

These go before the secondary phase, but after the bodyfit and measure merges. "Functionality buildout" below turns
them into work items.

## Generated references (2026-09-28, GPT Image 2.5 from the model sheet and the rig)

Six sheets are in `charkit/refs/clawd/gen/` (prompts in `prompts.json`), registered in the manifest with provenance and
cautions. The authority map is unchanged until each is checked against the sheet.

- **`head_turnaround`:** front, 3/4, profile and back of the head at about 4x the sheet's resolution. It's on-model, and
  the profile finally resolves the eye set-back, the pointed nose, the lips and the chin.
- **`head_construction`:** the bald head with guide lines (skull top, brow, eye, nose, mouth, chin), front and profile:
  the skull, the ear, and the face under the hair. It's the best profile reference we have. Caution: its front chin is
  more pointed than the sheet's.
- **`garment_breakdown`:** a labelled flat-lay. It has every piece the outfit graph found, plus the shapes our templates
  lack: the puff volume and gathers, the pleated cream panel, the stepped back-panel hems, and the cuffs' step motif.
- **`hair_breakdown`:** the hair's layers as colour families in three views, with a legend (bangs, side locks, upper and
  lower back, buns, ahoge, flyaways). Layers separate reliably; locks within a layer only partly.
- **`sleeve_closeup`** (second round, with `garment_breakdown` as an extra input): the puff sleeve on a mannequin arm,
  front, side and back. It shows the gathered cap at the armhole, the balloon volume, and the gathers into the cream band
  above the elbow. A cross-section shows how far the fabric stands off the arm; the wrist cuff's notch is shown front and
  side. The mannequin is generic: take the puff's size on the body from the sheet.
- **`skirt_closeup`** (second round, same inputs): the skirt on a mannequin, front, side profile and back, plus a
  top-down view of the panel order. It shows the knife-pleated orange outer skirt, the pleated cream front panel set
  into it, and the longer stepped under-panels at the sides and back. The side view gives the flare and the longer back,
  which is what our single stiff piece is missing. Caution: the top-down view is schematic (stepped edging on every outer
  panel), so use it for panel order and count only.

Use them in this order:
1. Check `head_turnaround` and `head_construction` against the sheet at its scale, which is the generated-view
   consistency check.
2. Make them the authority for face profile and skull (profile feature metrics, the midline profile target, eye depth).
3. Use `garment_breakdown`, `sleeve_closeup` and `skirt_closeup` for the piece-shape templates and checks (the skirt as
   separate pleated panels in layers, the puff's stand-off off the arm).
4. Use `hair_breakdown` for the hair component graph later.

None of this is built yet. It's item 1 of phase 4 under "Functionality buildout".

Michael's decisions on further generation (2026-09-28):
- **Mouth expressions:** standardize them in the template (a quality and detail pass); don't bring a generated reference
  against them.
- **Eyes:** `head_construction` already serves as the eye close-up reference, for the pupil, iris and sclera ratios.
- **Hair:** the layer sheet is enough for now. Lock-level labelling is a stretch goal for a later checkpoint.
- **Garments:** the sleeve and skirt close-ups were generated in a second round.

**Eye check against the construction sheet.** `charkit.eyeqa` measured three eyes the same way: the construction sheet's
front eye (the viewer's-left eye, at about 1.6x the rig's resolution), the rig's `eye_L` layer, and ours from `e2e/ck3_final`.

| measure | construction | rig | ours |
|---|---|---|---|
| opening aspect (h/w) | 0.922 | 0.925 | **0.685** |
| iris width / opening | 0.591 | 0.613 | 0.607 |
| pupil run (h / iris h) | 0.341 | 0.407 | 0.426 |
| pupil aspect (w/h) | 0.362 | 0.286 | 0.231 |
| pupil share of the iris (area) | 0.067 | 0.071 | **0.049** |

- The two design sources agree, so the design eye is confirmed.
- Our eye opening is about 26% too flat. `eye_aspect` already FAILs on this.
- Our pupil covers about 31% less of the iris than the design's, which is Michael's "pupils read small". Nothing grades it:
  `pupil_share` is measured but not in `eyeqa.compare`, and `pupil_aspect` passes at 0.81.
- Next: grade `pupil_share`, the "eye area ratios" item in the face-first priorities. Do it after the checkpoint's
  baseline, so the new check doesn't move the gate mid-sequence.

## Next steps, in order (the checkpoint)

1. **Merge `tool/bodyfit`** through the gate. Done: `77721ff`.
2. **Baseline full build test: done 2026-09-28.** It ran
   `charkit tune charkit/spec/clawd.json --out charkit/out/baseline --budget 8 --review --workers 3` in 44 min over
   6 builds.
   - Best: ck0, score 57.35 (the e2e run was 114.62), with 59 pass, 33 warn and 22 fail.
   - 57 work items in `charkit/out/baseline/work_items.md`, which is the baseline.
   - The VRM passes the validator with 0 errors and 0 warnings. The inspector loads it and matches Blender to
     0.75/255: `--loop='body~baseline/ck5_final~vrm:clawd'`.
   - It also exposed three tune bugs, now fixed on `tool/fitspeed` (below). The body fit ran for 30 min, and its
     block and half-step checkpoints (ck2–ck4) rebuilt ck0 unchanged.
3. **`tool/measure`: merged 2026-09-28 at `750a186`.** Blender time per build went from 123 s to 50 s; a full build
   plus QA is now about 35 s.
   - The first gate FAILed on four remeasured checks: the gate ran `pipeline-3d`'s `history.STEPS`, which lacks the
     branch's own steps. The gate now reads STEPS from the merged tree (`history.load_steps`). The second gate
     PASSed: 73 remeasured, none regressed.
   - Reports are in `charkit/out/archive/measure/`.
   - `bodyeval --validate` against a post-merge build passes (fixed on fitspeed: the Blender dump needed
     `qa3d_blender`).
   - Still to do: the confirming tune, after fitspeed merges **and after the reference work (3a)**.
3a. **The references, now (moved up 2026-09-28): phase 4's item 1, before the confirming tune and the review page.**
   The handoff put the face-first work after the bodyfit and measure merges, and both are done. As of the baseline:
   - `sheet_views` and `sheet_body` still use the 3D-style key (`spec.ref.image` resolves to
     `charkit/refs/clawd/clawd_3dstyle.png`), cropped by a fixed 30% head heuristic, not `idol_D`;
   - no code reads the six generated sheets, and the authority map is unchanged.

   **Michael's decisions (2026-09-28, second session): the generated references are the base; idol_D is not a
   benchmark.**
   - idol_D is drawn in a different aesthetic and at a different scale from the turnarounds. It is the **source
     design**: the input to the for-3D generation calls, and the authority for no measure.
   - What decides whether generated references can be trusted is their **internal consistency**: pairs of sheets
     view by view, and each sheet's views against each other. `charkit refcheck` (on `tool/refs`,
     `~/animation-pipeline-refs`) does this. How each sheet departs from idol_D is reported as information.
   - Authority (to wire into the QA):
     - the face (front, 3/4 and profile), the chin, feature heights and the midline profile → `head_turnaround`;
     - skull, ear and eye ratios → `head_construction`;
     - body and hair silhouettes, placement and palette → a generated full-body turnaround (`body_turnaround`:
       front, 3/4, side and back in one A-pose, one call, the views cut from the sheet);
     - the outfit → pieces cut from `garment_breakdown` and the close-ups, tagged and rigged independently;
     - expressions → a cross-character template library, with no reference comparison;
     - off-midline face depth and 3D hair shape → TRELLIS (a later TRELLIS run could be conditioned on the new
       turnarounds).
   - Refcheck on Clawd: `head_turnaround` and `head_construction` agree on the front width and on the profile's edge
     and reaches. The construction's chin is 0.034 L lower (its manifest caution), so the turnaround is the chin's
     authority. Both are consistent within themselves.

   Register every re-anchored check in `history.STEPS`, and measure against `charkit/out/baseline`: the confirming
   tune after it is the before and after. The review page (step 5) is built from the generated references.

   **Done on `tool/refs` (2026-09-28, second session), gating into `pipeline-3d`:**
   - `body_turnaround.png`: one GPT Image call (front, 3/4, side and back in one A-pose), generated from idol_D, the
     rig's front drawing, `head_turnaround` and `garment_breakdown`. Its prompt is in `gen/prompts.json`.
   - `charkit refcheck` (page: `charkit/out/refcheck/clawd/index.html`):
     - `head_turnaround` and `body_turnaround` agree on every face and eye check;
     - the body sheet's views share one eye line (0.009 L) and one ground line (0.017 L);
     - `head_construction` is the outlier on the chin (+0.03–0.05 L), the neck and the pupil's aspect (1.57x). An
       earlier "lid line 1.67x" was a crop artefact, fixed with a 0.18 x 0.15 L eye crop.
   - The manifest's `sheets` fill the 'sheet' role: face and eyes → `head_turnaround`; body, hair silhouettes and
     palette → `body_turnaround`. The eyes' authority moved from the rig; expressions have none. `qa3d.Design`,
     `bodymeasure.Sheet` and the outfit graph read them, each scaled by its own eyes (the kit's convention), with no
     rig and no idol_D in the scale chain.
   - `checks.authorize`: a check measured against a non-authority reference reads INFO (`ref_iou`, `shape_iou*`, the
     TRELLIS face-shape checks except depth, expressions). Steps are registered at `9307073`.
   - The review sheets (`sheet_views`, `sheet_body`) put the turnarounds over our boards.
   - The outfit graph was rebuilt from `body_turnaround`: field IoU front 0.85 and profile 0.76 (idol_D: 0.83 and
     0.72), 17 flags where there were 27. The TRELLIS field file must sit at
     `charkit/out/i3d/ext/runA/clawd_3dstyle_s1_field.npz` (restored from the archive).
   - On Clawd's current spec against the turnarounds:
     - `sheet_profile` FAILs (0.043), and nose and chin reach FAIL;
     - the eye opening is narrower than the turnaround's (0.79);
     - the buns sit 0.24 L low and the boot tops are off.
   - Known fragility: the fast evaluator and the QA can place our chin one pixel apart at 200 px/L. On the steep
     V-shaped jaw that moves `sheet_width` about 2%, which crosses its FAIL line (1.151 against 1.125).
3b. **The visual hull (`tool/hull`, `~/animation-pipeline-hull`; Michael, 2026-09-28: "much more promising than
   hacking detail into pre-provided single-shell meshes").**
   - `charkit/geom/hull.py` (`python -m charkit.geom hull SPEC`) carves Clawd's 3D shape from `body_turnaround`'s
     calibrated orthographic views. Details are in `docs/GEOM.md`, "Hull".
   - On the three-quarter view held out: 0.856 IoU. TRELLIS scores 0.79 and our build 0.68. The drawn views are
     0.96–0.985, and the surface is watertight.
   - **Style profiles** (`charkit/styles`, anime and realistic): Michael wants the kit usable for any 3D style. Stages
     read their priors from the character's profile. The hull does now; the planned drape and spring solvers' settings
     are declared there.
   - **The hull as the hair source:** the hull GLB, plus a sidecar with its exact eyes (`i3d.glb_eyes`; colour-found
     eyes on its smooth face shrank it). Compared with TRELLIS hair under the same QA:
     - the head's top (the buns) goes from FAIL −0.24 L to PASS in all four views;
     - hair IoU: front 0.49 → 0.77, three-quarter 0.49 → 0.71, back 0.64 → 0.91;
     - PASS / WARN / FAIL: 45 / 31 / 17 against 40 / 29 / 24;
     - hair length is 0.1–0.2 L short. The region cut stops at 0.33 L under the chin, and a deeper cut takes the
       top, which is the hair's orange.

     This is a decision for the review; the spec still uses TRELLIS.
   - **Michael's decisions (2026-09-28, after the hull):**
     - Order: per-piece carving, then a code-authored anime base fitted to the hull (the head and face structure
       first), then the drape and spring solvers on the style profiles, then the eyes.
     - **MakeHuman is retired.** The code-authored base replaces it, and the MakeHuman-derived anime base is dropped.
       Skeleton and weights come from our own rig code or are transferred once.
   - **Per-piece carving: done, gate PASS** (`tool/hull` at `a383c6b`; no check changed, all 20 test files ok).
     **Merge it into pipeline-3d once the confirming tune has finished**, not under it: the tune builds from that
     worktree.
     - The outfit's per-view piece masks are a produced reference (`outfit_masks`, built by its manifest command where
       missing: `manifest.produced`). A front run splits where an arm or a leg meets the body, and each limb part
       takes its depth from the side view's pixels of that limb, so the wrist cuffs stop taking the skirt's depth.
       The held-out three-quarter goes from 0.862 to 0.876.
     - The surface is labelled per piece: each shell voxel takes its label from the view facing it most squarely
       among those that see it, and the side views' mirrors label the far side. Written to `hull_pieces.npy` (per
       vertex, named in the sidecar), with the labelled shell in `hull.npz`.
     - Held out, the labels agree with the drawing 0.76–0.86 within 2 px; on the views used, 0.87–0.97. The limit is
       the input masks: the outfit field's votes are 0.77–0.85 IoU per view, and where two views' masks disagree about
       one surface, one of them loses. Improving those masks, for instance by making the hull the outfit's field in
       place of TRELLIS, is the lever.
     - The review page is `~/animation-pipeline-hull/charkit/out/hull/clawd/index.html`. It shows the held-out label
       maps next to the drawn ones, per-piece IoUs, the surface coloured by piece, and the limb maps.
   - **Checkpoint review page built (2026-09-28), `charkit/out/checkpoint/index.html`.** It compares before, reviewed,
     baseline, tune and now, with the decisions in `charkit/out/checkpoint/decisions.md`.
     - The confirming tune: 68.4 → 65.5 (41 / 29 / 23); the body fit was rejected for hair widths.
     - "Now" is the tune's best with the hull as the hair source (`charkit/out/checkpoint/now.spec.json`):
       **50 / 26 / 17**, 11 checks better and 2 worse. The worse ones are knock-ons of the cranium refitted from
       the hair: `eye_lid_span` and `face_shape_depth`, which is still graded against TRELLIS and should become INFO.
     - Per-piece carving is merged (`aa996f2`). Its outputs were copied in from the hull worktree; the old ones are in
       `charkit/out/archive/hull_prepieces`.
   - **Merged after the review (2026-09-28):**
     - `tool/review` (`0ddeb0b`). Michael: the hull is the hair's source, and the generated 3D character grades nothing:
       `face_depth` and `hair_shape` have no authority, so `face_shape_depth` and `shape_iou_hair` are INFO. The
       checkpoint page cuts design tiles to their own silhouettes and lists the checks that moved within their status.
       The hull hair took `sheet_shown_profile` from 0.18 to 0.016 inside WARN, which a status count hid.
     - `tool/chin` (`1660dbb`): our chin read with the design's rule (`faceqa.drawn_chin`). On today's build,
       `neck_to_jaw` goes FAIL → PASS and `width` WARN → FAIL: its jaw is wide once measured at the right rows.
     - The hull hair walls off the face in three-quarter and profile: no view shows the gap between the side locks
       and the cheek empty. Fix, after the head is in the build: class-consistent carving, where no hair lies in front
       of pixels a view draws as skin (the authored head gives the skin's depth).
     - Michael: the "now" build is the old methodology (MakeHuman head and body, knob-fitted garments, hull hair only),
       so it is no visual review of the new direction. The next review is a build with the authored head in it.
   - **Next: the code-authored head (`tool/head`, same worktree, branched from `a383c6b`).** At `5ef7423`, with the chin
     rule fixed, every sheet check passes but width (WARN 1.112): profile 0.003, profile_chin 0.005, nose_reach
     −0.001, chin_reach −0.001, cheek 0.005, cheek_chin 0.002, neck_to_jaw 1.05. The chin is warped 0.02 L past the
     design's (`CHIN_BIAS`: the QA reads the turn's start, which the rounding lifts).
     State at `4c4f7d2`, `python -m charkit.geom headfit SPEC --against charkit/out/now/qa/qa.json` (page
     `charkit/out/head/clawd/index.html` in the hull worktree):
     - **The approach:**
       - the skull is `head_construction`'s front and profile carved (guide lines painted out, ears opened off, no
         silhouette restoration), as polar sections per row, aligned to the face by the forehead;
       - the face is corrections on the skull's front that vanish at the outline: the turnaround's midline, a cheek
         term fitted per row to the three-quarter (below the eyes), and the nose and lips as relief;
       - the jaw rows are scaled to the design's outline, and the chin rows warped to its chin.
     - **Graded by the QA's own sheet comparison:** `sheet_profile` PASS 0.003 (the build: FAIL 0.042),
       `nose_reach` PASS −0.001 (build −0.053), `cheek` PASS 0.004 (build WARN 0.026), `chin_reach` WARN 0.034.
     - **The QA's chin rule is wrong for a receding anime chin** (it reads the chin, and places the width and neck rows
       from it). `sheetqa.measure_ours` reads our chin with `faceqa.chin_bottom`, which stops 0.06 L behind the
       lips. On this design that is −0.295; the drawn chin is −0.355. Our geometry matches the design's profile to
       within 0.002 L down to −0.34, yet `profile_chin`, `width` and `neck_to_jaw` FAIL. Today's head passes only
       because its chin juts (+0.042).
       - Fix, on its own branch and gate, since it re-measures every build: read ours with the design's rule. Move
         `refcheck.drawn_chin` into `faceqa` (refcheck imports sheetqa, so sheetqa can't import refcheck), and add a
         synthetic receding-chin test.
     - **Visible faults the checks don't measure** (so measure them first):
       - horizontal banding across the face. `banding()` is per-row second differences and is dominated by voxel
         noise; use a band-pass instead (the radius against a height-smoothed copy, over the face);
       - the jaw–neck junction: the neck reads as a separate cylinder under a flat under-jaw;
       - a groove at the eye line.
     - **Banding fixed at its sources** (`59edcdf`), measured by a band-pass (`banding()`: the radius against itself
       smoothed over 0.02 L of height). The construction profile's drawn lashes, nose and lips were spread across the
       skull's rows (`without_features` now smooths them off before carving), and the jaw's per-row scaling jittered
       with the pixel-quantised widths. 0.0049 → 0.0031, the carved skull's own level.
     - **The cage fitted without folds** (`465fbb8`, `headmesh.cylinder` + `headfit.cylinder_cage`). A box cage
       projected by rays folded 110–171 of 4680 faces where the box front was wider than the jaw. On the head's own
       chart (columns round it, rows down it, a dome of rays with a Coons cap at the crown) Clawd's cage (2737 vertices)
       has 0 flipped faces and 0 folded corners (`quality()`). The eyes' and mouth's loops land at their front-view
       outlines. The page shows it coloured by group.
     - **Fairness** (`2cd7943`; Michael saw lumpy cheeks, which no check measured). `normal_fairness`: the angle
       between each normal and its locally smoothed field, per region, with a map on the page. It's what shading sees;
       the outline and contour checks can't. The lumps were the cheek term, fitted row by row (amplitude −0.044 to
       +0.055 L between rows), now smoothed over 0.08 L. The midline correction is split into a broad part (smooth,
       spread across) and a narrow exact remainder (the nose, lips, bridge). The skull is analytic (`skull_analytic`:
       superellipses in the construction's silhouettes at 909 px/L, ears bridged, neck held, crown odd-reflected), with
       no voxel grain. Clawd: face 1.8° (the nose and lips), face sides 0.43°, cheeks 0.07°, skull 0.14°, jaw and neck
       0.93°; every graded sheet check PASS.
       - Carry fairness into the build's QA once the head is there, as a mesh-based `face_fairness_*`: vertex normals
         against their smoothed field over about 0.04 L. It would have caught this before a person did.
     - **Chin and neck** (`18b926c`, `c6b0fa7`; Michael: the chin read pointy and the chin-to-neck line wrong).
       Nothing graded below the chin, so `outline()` now overlays our silhouette on head_turnaround's drawn skin, front
       and profile, per row down the jaw, the chin's underside and the neck, and puts it on the page.
       - The fixes: each section's front narrows to the chin's V while its back keeps the neck's width. The chin's step
         under is kept sharp: the profile's front is smoothed piecewise and applied to the front only.
       - The back of the head narrows below the ears to the neck's width (`NAPE`), where it was hung on the neck like a
         cap on a stem.
       - The nape moves gradually and the neck's front only under the chin (a whole-neck move left a ledge).
       - The face outline bridges rows a drawn line cuts short, where a running maximum ran 0.012 L wide on the jaw.
       - Now within 0.023 L of the drawing everywhere below the face (it was 0.072), every graded sheet check PASS;
         fairness 4.0° on the jaw and neck, which is the corner under the chin that the design draws.
     - **The code base** (`cad6574`, `charkit/code_base.py`, `spec['base'] = 'code'`): the authored head on
       MakeHuman's body, with base_anime.wrap's contract.
       - The eyes get sockets and the mouth a cavity, labelled in eyes.py and mouth.py's form.
       - The body is cut level through the neck at `CUT` (−0.52 L). Faces over the cut that are joined to the head go.
         The head's neck eases into the body's section, and the rims zip by arc length in loop order: ordering them by
         angle skipped edges where MakeHuman's rim doubles back.
       - Weights ease from head to neck; the jaw region takes MakeHuman's `jaw` face bone.
       - `SectionsHead` gives the build `H` (eyes.Face takes it as is), and an affine landmark fit carries the joints.
       - Clawd assembles to one closed manifold skin. The first Blender build is `charkit/out/code_build` in the hull
         worktree, from `charkit/out/code_base.spec.json`.
       - Known to follow: the zip shows a faint seam at the neck's base, and the neck reads long in profile.
       - The fast body evaluator (`bodyeval`) still rebuilds a knob head when the body changes, so it needs a
         SectionsHead path before body fits run on this base.
     - **In a real build** (`4ef3b34`). `cli.code_head` computes the head venv-side into `out/geom/head_code.npz`
       (Blender's Python can't read the reference images). The eyes get sockets: the QA measures profile leads from the
       eye plates, which sat 0.028 L in front of the design's eye, and that read as a flat nose and an off profile. The
       cage is fitted to its Catmull-Clark limit surface. `hull.carve_face` clears the hull hair from in front of the
       drawn face (119k voxels on Clawd).
       - On the tuned spec with only the head swapped (`charkit/out/code_now` in the hull worktree): **55/25/11**
         against MakeHuman's 49/25/17. Every face check PASS (profile 0.009, nose −0.011, chin 0.004, width 1.07,
         cheek 0.012); eye_width PASS; face folds 1332 → 132; the face showing in profile 0.014 → 0.286.
       - Worse: eye_aspect 0.84 → 0.68 (the eye knobs were tuned on MakeHuman's head).
       - The review page is `charkit/out/checkpoint_code/index.html` in the hull worktree.
       - **Next:**
         - the hair as components (the hull hair is a helmet of slabs, the weakest part now);
         - the eyes on the new head;
         - face_folds 24 → 132 after the sockets and the limit fit: look;
         - the carve leaves a window in the hair at the temple and steps in the side locks;
         - the body authored like the head;
         - gate and merge `tool/head`, with `base: code` still opt-in until the review.
       - the eyes' and mouth's labels from the cage's loops, in `eyelib.labels` / `mouthlib.labels` format;
       - an `H` backed by the sections (`surfaces`, `sections`, `_xy`, `section`, the landmark attributes), with
         `eyes.Face` taking it as is: it rebuilds a `head.Head` from knobs today;
       - the neck's ring stitched to the body's neck (the body stays MakeHuman's until the body base is authored);
       - skin weights (head, neck, jaw), UVs (a front projection for the face), and the head's joints.
     - `python -m charkit.geom hull SPEC --head` carves `head_turnaround` (`views_from_heads`: 401 px/L, each view at
       its own eye row, which drift by up to 8 px; stopped at z = −0.66 L above the bust's vignette). Held-out
       three-quarter: 0.894 (plain 0.727). It is a silhouette and volume target (cranium, hair, the three-quarter),
       **not a face surface**: the section model takes each row's front from the profile's midline, so the nose, the
       lips and the drawn lashes push the whole row forward as ridges across the face.
     - `charkit/geom/headmesh.py`: the topology, authored in code. It is a box lattice whose front face is the front
       view's (x, z) plane. Each eye's and the mouth's block of cells becomes concentric loops, stepping in to the
       feature's outline, with a Coons-patch cap. A neck of rings comes out of the bottom face. It is all quads,
       manifold, open only at the neck's bottom (Euler characteristic 1), and every face is grouped (`eye_L_r0`…,
       `mouth_cap`, `neck`) for rigging.
     - **Next, `headfit`:** the face surface from the design's measured contours, the ones the QA grades:
       - the profile's leading contour, taken as the midline;
       - the front's face half-widths per row;
       - the three-quarter's leading contour, which fits each row's falloff from the midline to the side.

       The nose, lips and chin are local relief: the profile contour's residual against its smoothed base, spread
       across by a narrow falloff per region. The cranium sits inside the head hull's hair with a margin, with
       `head_construction` as the skull's authority.

       The cage's front face maps straight onto the face surface; the rest projects onto the cranium and neck. Then
       come the direct contour diffs, and the base swapped into the build (`spec['base'] = 'code'`, the head first,
       with the neck ring stitched to the body's) and graded by the QA.
     - Then the drape solver on the style profile, then the eyes.
   - **Fit speed (`tool/fitspeed`, `~/animation-pipeline-fitspeed`), in progress.** Done so far:
     - the body probe;
     - per-phase instrumentation;
     - the outfit draft as a measured start: it had reset the fitted garments on every fit;
     - list-aware knob paths for blocks and half steps;
     - the `bodyeval_blender` fix;
     - bounded evaluator memory: the hem textures shared, the garment cache capped;
     - `optimise(fast=)`: Broyden updates and a guided polish. It isn't the default until the Clawd benchmark
       agrees.

     The sparse-Jacobian idea is dropped: three whole-figure IoUs couple every figure knob (19 colours for 19
     knobs). The original plan:
     1. *The body probe.* `BodyFitter` inherits the face fitter's `sensitivity_at`, which reads `facefit.KNOBS`, so
        the body probe comes back empty. The tune then runs a full, uncapped body fit every round: 30+ min in the
        baseline, even where the fit can't pay off. Give `BodyFitter` its own probe from `bodyfit.knobs(spec)` and
        `terms(spec)`. That also restores the body's end-state table for the triage. Merge this before the
        confirming tune.
     2. *Instrument first.* Record evaluations and time per phase in the fit reports (sensitivity table, gradients,
        trust-region steps, pattern search, repair), and per evaluation stage (geometry, silhouettes, sheet, face,
        pieces).
     3. *Fewer evaluations.* The finite-difference gradient costs one evaluation per knob, and the pattern search
        tries every knob both ways. The changes:
        - group knobs that move disjoint checks into one evaluation (the sparse-Jacobian trick);
        - reuse the start table as the first gradient, with Broyden updates between full gradients;
        - rank the pattern search's candidates by the gradient's prediction.

        Acceptance: on a fixed start spec, the same QA result as today's optimiser, with the evaluation count and
        time reported side by side.
     4. *Cheaper evaluations* (after measure). Rasterise each view once with triangle IDs, and derive every label
        image from it. Today one evaluation rasterises the same geometry about 26 times.

     Measured 2026-09-28 on the baseline's start spec, one evaluation costs:
     - 2.7 s for a garment knob;
     - 4.8 s for a body knob (it rebuilds all 19 garment pieces);
     - 6.1 s for the full check set.

     About two-thirds of it is measurement. Three workers run the evaluations, limited by about 1 GB each on the 16 GB
     Mac, with 9 of its 12 cores idle.
4. **Clean up the merged worktrees:** fit, speed, tune, bodyfit and measure, once merged.
   - Archive the valuable outputs (gate reports, before/after sheets, fit reports) into
     `~/animation-pipeline-3d/charkit/out/archive/<name>/`. Earlier ones are already there.
   - Check `git status` for uncommitted work, then `git worktree remove` and `git branch -d`.
   - Never use `--slim` or `git sparse-checkout set` by hand in zsh: an unquoted `$var` is a single word there, and git
     deletes ignored-only directories outside the cone. `tools/worktree.sh --slim` now guards against this.
5. **Checkpoint review with Michael.** Make a local HTML review page and open it in the browser (`open`), not a list
   of file paths: the design sheet next to ours per view (front, 3/4,
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
   - **Height:** the body fit holds the head, so Clawd is 1.468 m and 5.87 heads (was 1.55 m, 6.2). Keep it, or free
     the head (`--free-head`)?
   - **Order after the checkpoint:**
     - the plan (written before the e2e review) put remote build scoping first, before any pipeline feature;
     - Michael's e2e review put the face first, before the secondary phase.

     This file follows the later call (step 6 before step 7). Confirm it, or move remote scoping up if build
     throughput is the bottleneck.
6. **Functionality buildout, face first:** the next section. It turns the review's face-first priorities and the
   plan's "Resume Clawd" phase into work items with deliverables and acceptance checks.
7. **Secondary phase**, only after that review:
   1. **Remote build backend (scoping) comes first:** a CPU spot VM for parallel builds, the existing L4 box for EEVEE
      renders, `charkit build --remote`, platform-keyed gate baselines, the same guardrails as the GPU box. New cloud
      resources only with Michael's go-ahead.
   2. **Motion QA:** range-of-motion and dance-clip sweeps. Measure interpenetration, stretch, joint volume and spring
      stability. The dance port's findings are the first targets: the arm through the top at frame 260, and the skirt
      at frame 200.
   3. **A generic path for untemplated parts:** the cleaned generated surface plus auto-rigging.
   4. **Spring bones:** VRMC_springBone export and runtime simulation, driven by the outfit graph's motion classes.
   5. **Generated-view consistency** for single-image input.
   6. **Hair as components:** ponytails, twintails, buns and locks, each rigged with its own physics.

**Motion-phase research (2026-09-29).**
- **UniMate** (github.com/Friedrich-M/UniMate): skip it as a tool.
  - It's a text-to-motion model for any skeleton, giving 2 s clips. It has no physics, cloth, spring bones or
    collision handling, which are our motion problems.
  - Its code is MIT, but its weights aren't cleared for commercial use: part of the training data is Mixamo, and
    Adobe's terms forbid using it to train AI. One dependency also has no licence.
- **Borrowed from UniMate** for motion QA:
  - normalise each pose (facing, grounding, scale) before the checks run;
  - add a foot-sliding check.
- **Candidates for the motion phase:**
  - **NVIDIA Kimodo:** humanoid motion from text plus keyframe constraints. The code is Apache-2.0, and its non-SMPL
    weights allow commercial use. It fits on the L4.
  - **Newton on NVIDIA Warp:** GPU cloth simulation driven from Python, Apache-2.0.
  - **Spring bones:** a numpy port of pixiv three-vrm's reference VRMC_springBone implementation (MIT).

## Functionality buildout (after the checkpoint review)

The plan's sequencing had four phases, each ending at a gate:
1. build the tools in parallel;
2. merge them in order (Gate 2: "Clawd rebuilds on main, QA no worse than today");
3. wire them into `charkit build` (Gate 3: "one command builds Clawd end to end");
4. resume Clawd.

**The end gate: every Clawd check PASS or WARN, and the dance demo approved.** The toolkit round covered phases 1
and 2. Phase 3 is partly done. Phase 4 is the character buildout itself: the face-first work, garments, then the dance
demo.

### Phase 3, wiring: where it stands

| Plan item | Status |
| --- | --- |
| Hair and skirt from TRELLIS parts, cleaned by the kernel | Hair: done (`--hair geom`, accepted in the e2e tune). Skirt: not started; its geometry is still the parametric template |
| The anime base as the default for new specs | Built, not the default. It was rejected in the e2e tune (eye width, iris ratio, laugh mouth, neck-to-jaw). A review decision (step 5) |
| Export the .glb; review boards drawn by the WebGPU renderer | Export: done (the VRM passes the validator with 0 errors and 0 warnings). WebGPU matches the Blender boards to under 1.1/255, but the build's review boards are still Blender renders |
| QA metrics and overlays in the inspector | Done |

Gate 3 is met: `charkit tune --review` takes the spec to a fitted, QA'd and exported build.

### Phase 4, in order

Each item follows the rules: measure first; a reference grades only what the manifest makes it the authority for; new
checks are registered in `history.STEPS` so the gate reads them as remeasured, not as regressions; every new check gets
tests in `charkit/tests/`. Build the checks after `tool/measure` merges, on the geometry bundle, so they're written once.

1. **Generated references become authorities** (the review's items 1 and 7). The six sheets in
   `charkit/refs/clawd/gen/` are registered but grade nothing: no code reads them, and the authority map is unchanged.
   1. *Consistency check.* Compare each generated sheet with `idol_D` at the sheet's scale: silhouettes and landmarks
      per view, with a report per reference. It's the first slice of the secondary phase's generated-view
      consistency. Acceptance: `head_turnaround` and `head_construction` agree with the sheet within the existing
      `sheet_*` PASS limits in the views they share, and the known caution shows (`head_construction`'s front chin is
      more pointed).
   2. *Authority map* (`manifest.json` `authority`), only for the sheets that pass:
      - face profile, skull and eye depth → `head_construction` / `head_turnaround`;
      - eye ratios → `head_construction` (it agrees with the rig: opening aspect 0.922 vs 0.925);
      - new entries for garment piece shape → `garment_breakdown`, `sleeve_closeup`, `skirt_closeup`;
      - hair components → `hair_breakdown`, later.
   3. *Single-authority grading.* Make `ref_iou` INFO, and `shape_iou` INFO outside TRELLIS's authority (depth and
      hair). Rebuild `sheet_views` and `sheet_body` on `idol_D`'s own figures, matched per view and scale; today their
      reference column is the 3D-style key made from the rig.
   4. *Review input.* Notes anchored to a region and view on the board, with a severity, so each note maps to a check.
      Acceptance: each of Michael's e2e notes maps to a check whose status matches his severity.
2. **Face profile** (the review's item 2).
   - Build the feature metrics against `head_construction`'s profile: nose-tip projection, nasion depth, lip and chin
     projection, the jaw angle, the forehead slope, the eye's set-back from the brow-nose line, slope and curvature
     along the profile, and the worst deviation.
   - Then add the head-shaping capability: fit the midline profile spline to the design's profile, set the eye's
     depth, and give the nose, lips and chin structure. The `nose_tip` knob is capped at 0.04 L.

   Acceptance:
   - the metrics FAIL on today's build, where `sheet_profile` says 0.039 L WARN and Michael says "catastrophically
     off", so the measurement agrees with his eye;
   - then they PASS after the capability, and he agrees at review.
3. **Eyes** (item 3). Grade `pupil_share`: the design's pupil covers 0.067 of the iris (construction sheet) or 0.071
   (rig); ours covers 0.049. Then fix the pupil and the opening's aspect: 0.685 against the design's 0.922.
   Acceptance: `pupil_share` and `eye_aspect` PASS, with pupil run and lid gap held. They trade against each other
   today.
4. **Review calibration and a perceptual metric** (item 4). Weights and limits come from Michael's severity calls.
   Try DINOv3 features per view and region as a complement.
5. **Mouth** (item 5). A quality and detail pass on the expression template: standardize the mouths in the template,
   with no generated reference (Michael's call). Face folds are 1321, mostly from the laugh, yawn and wavy mouth keys.
   Acceptance: the `expr_*` checks hold, and face folds drop.
6. **Garments** (item 6; the plan's "seed garments from TRELLIS parts").
   - Per-piece shape checks from the outfit graph's per-view piece masks.
   - The skirt as separate pieces in layers:
     - the knife-pleated orange outer skirt;
     - the pleated cream front panel set into it;
     - the longer stepped under-panels at the sides and back.
   - The puff sleeves: the gathered cap, the balloon stand-off from the arm, the gathers into the cream band, and the
     cuff's notch.

   Acceptance:
   - the pleat and panel counts match `skirt_closeup` (its top-down view gives only the order and count);
   - the stand-off matches `sleeve_closeup`'s cross-section;
   - sizes on the body match the sheet.
7. **The dance demo** (the plan's last phase-4 step). Finish the dance port (below) after the secondary phase's motion
   QA and spring bones, which measure what the port found by eye. Render the full clip for Michael's approval.
8. **Hair components and the hair rework** (item 7): strands, chunks and layers from `hair_breakdown`, after the face.
   Lock-level labelling is a stretch goal for a later checkpoint.

### The dance port (`885d53c`)

`projects/clawd3d/shots/dance_charkit.py` (the shot) and `charkit_rig.py` (its helpers) put charkit's Clawd through the
old dance test: TSUZUKU bars 58–66, the same clip, camera, stage and lip-sync. A subagent built them. It was stopped on
purpose when Michael paused the Clawd demo for the toolkit round, and its files stayed uncommitted until `885d53c`.

- **State.**
  - Six stills are rendered in `projects/clawd3d/out/dance_charkit/stills_post/` (gitignored; the best are 0140, 0230
    and 0290).
  - The full 295-frame clip was never rendered. Estimate: 15–18 min plus 1 min of post.
  - Run it with `blender -b --factory-startup --python projects/clawd3d/shots/dance_charkit.py -- OUTDIR`, then
    `projects/clawd3d/shots/encode.sh OUTDIR`.
  - `--charkit HEAD|live|REV` pins the charkit a shot is built with.
- **Written against charkit before the toolkit merges.** Bodyfit's rest-pose knobs (arm_down 11.1°, leg_in 5.7°,
  elbow 2.2°) change the A-pose its calibration assumes. Re-check the calibration and the floor lock on the current
  stack before a full render.
- **What it found:**
  - All 52 bone names match the old bone map.
  - Charkit's torso bones lean off the body: the hips 35° back, the neck 60° forward, the head 23° back, the
    clavicles about 25° off. So the calibration aims only the limbs, hands and fingers, and treats the torso as
    already matching the source's rest.
  - The floor lock runs on the shoes: the soles sit 9 mm below the floor at rest.
  - The springs are added shot-side: three hair pendulums from the crown, rising from zero at the eye line, and one
    skirt pendulum, 45% at the hem.
  - The face light needs the head's rotation from rest, not the bone's world matrix.
- **Seen in stills, not measured** (motion QA's first targets):
  - arm skin through the top when an arm crosses the chest (frame 260, shoulder skinning);
  - the skirt deforming a lot when a thigh lifts (frame 200);
  - collar nicks near the neck, and the cream panel's jagged side edges;
  - spring motion never reviewed as motion.
- **Charkit fixes it recommends** (status checked 2026-09-28 on `885d53c`):

  | Fix | Status |
  | --- | --- |
  | The hair's shading helper is rigged to the head, so the hair's shading drifts as the head turns: bake `volume_normals` at build time and drop the helper | open (`scene.py:294`, `:320`) |
  | `bow()` is weighted entirely to `upperChest`: use nearest body weights, as `collar()` does | open (the shot does it) |
  | The collar offset 0.03 L touches the top: sit it outside the top (0.012 + 0.01 L) | open (the shot pushes it out 2.5 mm) |
  | Panel UVs use a per-face front test (`mean y < cyf + 0.02`), which makes jagged edges: project per corner | open (`garments.py:655`) |
  | `faceshade.set_light` should ask for the rotation from rest, or take the armature | open |
  | Outline thickness as a parameter: 1.1–1.4 mm is under a pixel at full-body framing | open (hard-coded at the call site) |
  | Keep the neck and head bones near upright, or ship `charkit_rig.calibrate` as a charkit helper | open |
  | Move the springs into charkit, and fix the shoulder skinning | open (secondary phase: spring bones) |
  | `hair.py`'s "Mean of empty slice" warning | probably open (`errstate` doesn't silence it) |

## Checkpoint 2026-09-30, morning (read first; paused near the usage limit)

**Merged into pipeline-3d today** (each gated on both specs):
- hair round 3 (e11fadb);
- hull limb labels + the bare-leg check + docs/HULL_CONTRACT.md (a524c3b);
- bucket sync (11f95b6);
- our toon renderer phase 1 (charkit/render, wgpu; 6be2b39);
- the perceptual metric (8ae6ce9; failed its calibration, kept as INFO heat maps);
- infra: preview, registries, 2x2, evaldrift (cfcdc3a);
- single geometry source, pilot (8a7d4ea).

Michael's calls H, I and J are in "Michael's calls" below. The first combined preview is
charkit/out/previews/cfcdc3a/review.html (179 PASS / 27 WARN / 7 FAIL; the previous one, at 9397578, was 176 / 29 / 8).

**The post-merge preview hook is REMOVED.** Git exports GIT_DIR to hooks, and preview._git inherited it. The hook's
preview therefore ran `checkout -f --detach` in the pipeline-3d worktree, not in ../animation-pipeline-autopreview, and
built stale code. tool/infra2 has the fix (strip GIT_* from the env). Reinstall the hook
(`python -m charkit preview hook install`) only after it merges; until then run `python -m charkit preview` by hand
after merges.

**Branches at checkpoint:** each has its notes in docs/workstreams/NAME.md; relaunch lean from them. Integrator
decisions already made:
- **tool/face (round 3): MERGED (bbf1c04).** The notch 0.057 -> 0, jaw_line_bend 41 -> 4.6, with the accepted chin 2x2
  drops (chin_angle 116.7 in the boards' camera, about 126 level; design 129.7). **Next face round:**
  - recover the chin (crease the V's point in character.py, or denser cage columns);
  - the ramus behind the jaw angle;
  - **120 inward-facing skin triangles at the crown**, which make the default spec's hair_penetration 0.0124 FAIL a false
    reading (found by tool/hair4);
  - sheet_width's +0.023 evaluator drift.
- **tool/look3 (calls H and I): MERGED (18b740a).** Streaks now agree across GPUs and renderers (IoU 1.000 / 0.995).
  Thin garments are fully inked. **Open for Michael** (look.md round 3):
  - the rim beads: a cap of 0.3 or 0.2 of the shell (214 / 84 flips left), or flat rims from the garments side;
  - caps for the bow and boots at half their measured thickness (501 -> 144 and 226 -> 78 flips);
  - a streak seed, if the big highlight on the right bun reads wrong;
  - the garment line weight: ink area +21-30% now that the lines draw at full width; the multiplier is the dial.
- **tool/hair4: checkpoint bb189f9, not gated.** Defaults: body clearance (clawd_mh hair_penetration 0.0484 -> 0.0034)
  and the crown trim (upper back 0.771); buns 0.397 -> 0.437. Behind settings: shell samples (stable, but folds 6 -> 12
  on this bundle) and the outline-weighted bun fit (0.50, costs the back view). Next: merge pipeline-3d, gate, review
  page.
- **tool/skirt: checkpoint 73fe12c, not gated.** Template flaps and stepped band, tuck and 18 pleats, built on the box:
  flap profile IoU 0.25 -> 0.71, band steps PASS, back gap PASS, tuck PASS. Next: write fit G into the specs, merge
  tool/garments2 (see below), flapchains, gate both together.
- **tool/toonrender2: checkpoint 0b16765, not gated.** The QA can draw with charkit.render (`CHARKIT_QA_DRAW`), and its
  head pictures sit half as far from EEVEE (0.84-0.91 levels against 1.6-2.1). Default unchanged. Next: merge look3,
  recalibrate the noise, add clawd_mh, time the build box, decide the default.
- **tool/garments2** (jacket over band, 2bf75d1; gated 3d81679): Michael's flag is fixed (the over-band check 0.97 FAIL
  -> 0 PASS, piece_waistband 0.45 FAIL -> 0.89 PASS). MakeHuman gate PASS; **default gate FAIL, merge held**:
  - body_front_skirt_overhang_L/R 0 -> 0.118/0.115: the band now has its drawn width, and the skirt's tuck follows the
    hull's band label, which the drawn masks put about 0.09 L too high at the sides;
  - body_front_torso_jump_L WARN;
  - 2x2 drops: bow_profile_torn 0 -> 0.018 FAIL, bow_front_tail_gap WARN, sleeve_profile_rough_L WARN.
  **Plan:** tool/skirt merges tool/garments2 into its branch, tucks the skirt under the band garment's bottom row, and
  both land through one gate. Decide the bow and sleeve 2x2 drops then. At merge, drop garments2's edits to the
  evaluator's garment dispatch (geom-truth removed it; this includes the collar-stripe tone) and keep a single
  `hem_drop` in the shorts entry.
- **Cross-cutting, from garments2:** the garment builders' eye line (the eye knobs) sits 0.0235 L below the QA's (the
  irises), so every garment lands that much low in the checks. Fix it in one place, not per garment. Our shoulders sit
  0.06-0.09 L below the drawn collar line (tool/body), which blocks the sailor-collar template.
- **tool/artifacts**: flag-calibrated checks capped at WARN, the rest INFO. MakeHuman gate PASS.
- **tool/hair4** (buns, crown, MakeHuman shoulder clearance, placement off the decimated mesh). Accepted at the
  hull-limbs merge, fixed here: clawd_mh hair_penetration 0.0484 FAIL, and hair_folds 4 -> 11.
- **tool/skirt**: the flap train touches the back of the thigh (body_profile_leg_outline 0.57, 82 rows against the
  design's 3); clawd_mh body_three_quarter_skirt_aline 0.078 WARN is accepted and belongs here.
- **tool/outfit-source**: masks without the TRELLIS field (or the field made a required produced reference).
- **tool/artifacts: MERGED (815c836).** Twelve of Michael's flags are calibrated checks, capped at WARN. **Promote to FAIL
  next** (the bad build reads at least 2x the clean one, and the current build passes): spikes_boots, bumps_boots,
  bumps_legs, mirror_waist. Hold points_sleeves/bumps_sleeves at WARN until garments2's template sleeves merge (the
  current hull sleeves would FAIL), and band_lower until tool/skirt's band lands. Not measurable by these detectors: the
  rear tuck (tool/skirt), jacket over band (garments2), the neck nick (tool/face's jaw_line_bend). Review page:
  ~/animation-pipeline-artifacts/charkit/out/artifacts_review/flags/index.html.
- **tool/infra2**: detached box jobs, box load logging, click-to-flag (`charkit preview serve`), the hook fix.
- **tool/toonrender2**: the QA drawing on charkit.render behind a setting.
- **tool/evalmesh** (call J, subdivision and Solidify into the venv): stopped before any work. Relaunch from
  docs/GEOM_TRUTH.md step 7.
- **Second-character checkpoint** (side quest, uncommitted; the character's files stay untracked because its project
  is unpublished): its worktree and page are in the integrator's memory, not here. First
  generality reading: QA pass share 30% against Clawd's 83% on the same code, and none of the references reached the
  model (it built the MakeHuman default). Generic blockers, in order:
  1. reference detection (views, eyes, hair) tuned to Clawd's colours; a floor line merges the views;
  2. outfit pieces need a hand-built 2D rig;
  3. 84 of 270 checks are named for Clawd's pieces, and the colour classes and hair families are fixed;
  4. hand-written garment lists, and no builders for a tailcoat, two-sided material, trousers, a braid, an ear cuff or
     a pin; one iris texture for both eyes;
  5. hazards: a misread scale ran a QA step to 68 GB on the build box (a 6-line guard in sheetqa.py, uncommitted in that
     worktree; land it generically), and a build that ignores every reference still reports success.

## State at the end of 2026-09-29 (read first)

- **The default spec is the authored character** (`8e2797e`): `charkit/spec/clawd.json` is the code-built head and
  body with hair pieces. The MakeHuman base is `clawd_mh.json`, and `clawd_body_pieces.json` is an identical alias
  (edit both until the notes stop naming it). On the default spec: 91 PASS, 20 WARN, 9 FAIL.
- **Merged today:**
  - body rounds 2 and 4 (Michael: "much better"; the pleated skirt a "massive improvement");
  - the look (camera key, ink lines, face shadow) and its QA speedup;
  - hair detail (block buns, fringe);
  - render batching (boards 2.3× faster, bit-identical);
  - references extension (off);
  - stamps covering file inputs;
  - loft robustness;
  - parallel gates (CPU-time slowness check);
  - unshare;
  - the sync fixes.
- **Two root causes found today; don't reintroduce them:**
  - A sync from a worktree without `charkit/out/i3d` wiped the box copy's. The outfit masks were then built without
    the TRELLIS field: a wrong hull, and `garments.sleeve_hull` failing. Sync now leaves `i3d` alone and seeds it, and
    new worktrees clone it.
  - The masks' stamp didn't cover that field (tool/stamp-spec fixes this). Worktrees seeded with `cp -al` rewrote
    produced files through hard links (cache.unshare fixes this).
- **Concurrency:** about 5 lean agents at once. The five-hour usage limit is shared with Michael's other sessions,
  and 13 at once used 63% of it in 100 minutes. Pause to notes and relaunch lean, per the memory note.
- **Running at the end of the day:**
  - tool/face: the chin and jaw overhang;
  - tool/eyes2: profile gaze and pupil shape;
  - tool/hull-det: bit-identical hulls on three machines;
  - tool/body round 5: the midriff seam, and boots rebuilt as a template (heel, scrunch, flat symmetric sole, no
    doubled toe line).
- **Paused, each with a notes file with state and next steps:**
  - tool/look2: cast shadows built but not validated; `docs/workstreams/look.md` "Paused";
  - tool/rig: R1 and all volumes PASS; sleeves at a raised arm and a cache test left; `rig.md`;
  - tool/hull-limbs: side-view limb labels; a gate regression to attribute; `hull-limbs.md`;
  - tool/artifacts: jaggedness detectors; both gates PASS; fix the design-measure stamp first; `artifacts.md`;
  - tool/accessories: an 8-point star and the crab, placement fit unfinished; `accessories.md`;
  - tool/perceptual: DINOv3 review metric, calibration not yet run; `perceptual.md`;
  - tool/hair3: fragments and edge measures done, fixes next; `hair.md` "Round 3";
  - tool/mouth: a mouth lab, laugh and yawn refit, new mouths started; `mouth.md`;
  - tool/motion: ring constraints and foot IK, ungated; `motion.md`.
- **Michael's calls (2026-09-30, from the decisions page):**
  - A. board light: the camera key (`look.light.mode: camera`, 30°/40°), already the default;
  - B. outlines: ink on hair, garments and accessories, the skin warm brown, 0.22%, already the default. Line
    thickness is a per-production taste choice: keep it a style setting (`look.lines.frac`, per-region multipliers).
    A future production can set its own.
  - C. eye flatness: (a), the design's plane (coordinator's call; the eye surface builds on it);
  - D. brow: (a), the slight recess under the fringe (coordinator's call). It's the forehead's fixed shape under the
    bangs, not brow motion.
  - Michael envisions a modular expression system (eyes, brows, mouth and face moving as combinable components). The
    expression keys already work that way. tool/mouth's relaunch should build toward it, with the rest face as one
    preset.
  - E. flap train: hang (the current default);
  - F. hair relief and clamp: deferred until relevant;
  - G. Kimodo licence: deferred until motion options are reviewed.
  - H. hair streaks (from tool/toonrender): replace the `sin()` hash, whose large angles every GPU rounds differently, with
    an integer hash. The streaks then fall in the same place in EEVEE on every GPU, in charkit.render, and in look.js.
  - I. screen-width lines on thin shells (from tool/toonrender): the outline's inward move is capped at half each
    piece's shell thickness, and the rest of the line width goes outward. The shells no longer turn inside out
    (garments are 1.5-3 mm thick, the move was 3.6 mm), and thin pieces' silhouettes grow by a fraction of a pixel.
  - J. subdivision and Solidify (docs/GEOM_TRUTH.md step 7) move out of Blender into the venv: no reason to keep them
    there. They're computed at rest and then skinned (the game-engine way; the VRM export needs final meshes anyway),
    and the motion QA checks the bends at extreme poses against Blender's per-frame modifiers. The outline's inverted
    hull stays render-time (call I), not geometry.
- **Follow-ups not assigned:**
  - key gate baselines on the produced references' stamps;
  - make a missing TRELLIS field fail loudly;
  - benchmark the render box's SLOTS;
  - prune the box's temporary copies (bis*, stampspec-*, render-*).

## Process and architecture decisions (Michael, 2026-09-30)

Drawn from the session's recurring failure patterns:
1. **Templates first.** Garments, and any other part a template can describe, are built from a few parameters fitted
   to the design's per-view silhouettes (the boots and puff sleeves are the model). The hull gives initial guesses,
   depth and measurement, not surface geometry. Geometry lofted straight from the hull caused spikes, twisted soles,
   doubled lines, torn tips and bubble skirts.
2. **Michael's flags become regression tests,** and every new check ships calibrated: it passes on the design itself
   and fails on a known-bad example. After every merge to pipeline-3d, a combined preview and review page (design |
   previous | current) is rendered automatically, so review never depends on someone asking for it. The artifact
   detectors and the perceptual metric are relaunched when there's room.
3. **No gaming.** Every fit includes its piece's shape (IoU in all views) alongside the check it targets. When a check
   is remeasured in a branch that also changes geometry, the gate scores the new geometry under the old measure too
   (the 2×2).
4. **Less coupling.** QA parts and measurement steps register themselves, with no central lists to conflict on. The
   hull has a written contract (its outputs, labels and guarantees), and downstream work pins a hull version within a
   round. Ownership is in `docs/OWNERSHIP.md`.
5. **Trustworthy local loops.** A standing test compares the numpy evaluator against the box on the same build, so
   drift like the 0.024–0.028 L hem offset shows at once. Review close-ups use the design's own projection (level,
   orthographic), not the boards' elevated camera.
6. **Process.** A lean agent per round, briefed from its notes; about 5 at once; no polling; milestone reports;
   smaller, more frequent merges.

## Parallel workstreams (2026-09-29): read this first when resuming

Michael's next steps after the code-authored head: cut-piece hair and garments, the eye and mouth engine overhaul,
aesthetic quality tuning, more expressions. They run in parallel, each in its own worktree and branch, building and
gating on the build box (below). The integrator (the main session) reviews and merges them. Each keeps its notes in
`docs/workstreams/NAME.md`, and they're folded in here at merge.

| workstream | branch / worktree | state |
|---|---|---|
| cut-piece hair | `tool/hair-pieces` | **merged at `5206150`**: `docs/workstreams/hair.md` (taste calls for Michael there) |
| eye and mouth engine | `tool/eyes-mouth` | **merged at `dd7eb32`**: `docs/workstreams/eyes.md` (taste calls for Michael there; the authored-head spec is `charkit/spec/clawd_code.json`) |
| garments as pieces | `tool/garments` | **merged at `8f2ec5d`**: `docs/workstreams/garments.md` |
| the authored body | `tool/body`, `~/animation-pipeline-body` | **round 2 merged at `76d5bdc`** (default-spec gate PASS). `clawd_body.json` isn't the default yet: its gate FAILs on `body_three_quarter_hem` (the overskirt panels, awaiting Michael's call on what they are) and `poke_share` (wrist cuffs with no clearance). Cuffs, back skirt width and chest/waist checks are in progress: `docs/workstreams/garments.md` |
| hair detail | `tool/hair-detail` | lock relief and the buns as drawn loops, not hull blobs: `docs/workstreams/hair.md` |
| face: eye hollow, neck, chin | `tool/face` | in progress |
| better references | `tool/refs2` | extra design views (three-quarter back, top) by anchored edit; drift measured; one call versus several A/B |
| shading and lines | `tool/look` | face shadow map, outlines, highlights |
| motion groundwork | `tool/motion` | motion QA sweeps (with UniMate's pose normalisation and foot sliding) and spring bones |
| render batching | `tool/render-batch` | board stills batched into animation renders: 2.24 → 0.53 s a frame, bit-identical (measured on a saved Clawd scene) |
| vertical slice | not started | scoped in `docs/SLICE.md`: one action beat end to end, with physics dials; starts after its rig gate R1–R6 |
| hull determinism | `tool/hull-det` | bit-identical hulls on the build box (AVX-512), render box (AVX2) and laptop (ARM). The carved volume already matches; decimation order and the labels' view choice diverge on last-bit float ties (3% of vertex labels) |
| rig adequacy | `tool/rig` | the slice's start gate R1–R2 by motion QA: spine rest, weights (sleeves, collar, fingers), elbow and knee volume (twist bones and constraints, correctives) |

**Box infrastructure (2026-09-29, later).**
- **Parallel gates** (`f3e8747`). Each gate runs in its own `git clone --shared` of `/srv/work/repo`, with the lock held
  only while fetching. Outputs go to the shared `/srv/work/gate-out`, and gates into one commit build its baseline once,
  under a lock of its own. Only the gate's own report comes back: fetching all of `_gate` had been 673 MB a gate.
- **Gate code comes from `into`.** A gate runs the target branch's `gate.py`, not the gated branch's, so a change to
  gate.py only takes effect once it's merged.
- **Syncs leave gitignored paths at home** (`6c78048`): a full worktree's first sync went from 2.7 to 0.87 GB.
- **Hard links:**
  - Worktrees seeded with `cp -al` shared the hull and outfit masks, and rebuilds wrote through the links: the face
    fork's carve landed in four other worktrees.
  - `cache.unshare` (`tool/unshare`) makes produced references and build outputs unshare before they're rewritten.
  - Never seed charkit/out with hard links except `i3d`, which builds only read.
- **Cross-machine hulls:** same code, different CPU gives different hull labels (see `tool/hull-det`). Each box is
  deterministic run to run. Compare only builds from one machine until hull-det lands.
- **New worktrees** need `infra/gcp/build.env` and `render.env` copied in (gitignored).

**Render box facts (2026-09-29).**
- A Clawd board frame (540x900, EEVEE, 64 samples) takes 2.4 s on the L4, 2.2 s on a T4 and 2.0 s on the M2 Pro
  laptop. It's CPU-bound, because each still re-evaluates every modifier: 51 armature, 47 solidify, 20 subdivision
  and 9 data-transfer. The render box adds parallel slots and takes load off the laptop; it doesn't make a frame faster.
- When L4s are stocked out, `up` switches the stopped box to n1-standard-8 with a T4 (`infra/gcp/gpu-start.sh`,
  `reshape.py`), and switches back once they're in stock.
- `gpu.sh snapshot` and `gpu-provision.sh --zone Z --from-snapshot NAME` recreate the box in any zone.

Merged this session, besides the build box:
- `tool/stamp` (`d71e2ba`): a produced reference's stamp follows its producer function one import deep (it had
  reached all of charkit, so any edit rebuilt the hull in every worktree).
- `tool/produced` (`56e1375`): produced references (the hull, the outfit masks) are stamped with their producer's code
  and inputs, and rebuilt when stale. pipeline-3d's hull had predated the face carve.
- `tool/garments` (`8f2ec5d`):
  - the outfit measured piece by piece in 2D (`piece_*`) and in 3D (`piece3d_*`), with the `charkit pieces` review
    page;
  - the waistband, skirt, top hem and bow taking their shape from the visual hull (`geom.loft`, `source: "hull"`).
  - Box builds: PASS/WARN/FAIL 49/28/33 → 54/32/24.

**The finding that sets the next step:** a piece lying on the body at the design's surface ends up inside the
MakeHuman body, which isn't the design's. Under the top, our torso stands out of the hull by 0.077 L (median; 86% of
points by more than 0.02 L). The collar, a hull-true top, the sleeves and the cuffs need the authored body fitted to
the hull first. The hull shows only 29% of the torso (the lower bodice and the waist), so the plan is a parametric
torso anchored to what it shows and bounded by its envelope, plus limb tubes on the graph's skeleton. On Clawd every
join is hidden under a garment (puffs, shorts, cuffs, boots), so the parts can start separate. See
`docs/workstreams/body.md`.

## Remote builds: the build box (2026-09-29)

Builds, tunes and gates run on a CPU box in the research project, not the laptop. Michael approved it on 2026-09-29.
- 32 vCPU and 128 GB, with Blender at the laptop's version, headless. It shares the GPU box's isolated network, service
  account and bucket.
- The real names are in the gitignored `infra/gcp/build.env`: copy `build.env.example` and fill it in.
- It stops itself after 30 idle minutes; any `remote` command starts it again.
- It skips the boards (`CHARKIT_NO_RENDER=1`): software EEVEE takes minutes a board, and the QA doesn't read them.
  Render boards locally or on the GPU box when a human needs them.
- A remote build matched a local one on 33 of 36 checks; the three hair checks differ by at most 0.002 (x86 against
  arm64). Compare remote gate reports against remote baselines only.

```
python -m charkit remote build SPEC --out charkit/out/X [build flags]  # syncs this worktree, builds there, fetches --out
python -m charkit remote tune SPEC [...]                               # the same for a tune
python -m charkit remote gate BRANCH [--into pipeline-3d]              # the gate there; the report lands in charkit/out/gate
python -m charkit remote run CHARKIT_ARGS...                           # any charkit command in the box's copy
infra/gcp/build.sh sync . && infra/gcp/build.sh run . 'python -m charkit.geom headfit ...'   # any command
infra/gcp/build.sh status | up | ssh | stop
```

How the gate gets its code:
- The box keeps one clone (`/srv/work/repo`). A gate sends a git bundle of only the commits that clone lacks. The
  first bundle is the whole history, 1.8 GB; later ones are small.
- **Bulk data goes through the bucket, not the IAP tunnel** (`charkit/bucketsync.py`, merged 2026-09-30). Syncs,
  fetches and pushes go through a content-addressed store (`cas/<aa>/<sha256>` blobs, manifests, named pointers) in
  the existing bucket; ssh stays on IAP for control. A box fetches missing blobs inside GCP (884 MB in about 6 s),
  reuses matching files from its own copies before asking the laptop, and hard-links inputs from a read-only blob cache
  (always replaced by rename, never written through). Outputs are never linked. A fresh copy syncs in about 3 s
  (rsync: 5-8 min). Builds and gates publish their outputs in-session and the laptop pulls them.
- The slow link is the laptop's upload (about 1.8 MB/s either way), so new content costs the same once, and then
  never again for any worktree or box. A saturated uplink is what dropped IAP ssh ("not responding").
- `CHARKIT_SYNC=rsync` keeps the old rsync-over-IAP path (with its hard-link seeding and the `charkit/out/i3d` rule).
  `infra/gcp/build.sh verify WT` compares a box copy with the worktree file by file.
- Gates from several worktrees run in parallel, each in its own clone, with a lock per baseline.
- Open: bucket garbage collection (about 1 GB of blobs now); ssh multiplexing (1.2-3.8 s per IAP ssh).

The box runs 8 build slots, shared by every worktree's builds there. **The laptop runs 1** (`charkit slots 1`): other
sessions share its 16 GB.

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

## Production principles (Michael, 2026-09-29): the RWBY bar

The quality bar is the early RWBY trailers. Monty Oum made them with a bespoke pipeline bent to one vision, which is
what we're building too (his write-up: "The 3D secrets behind hip anime series RWBY", 3D World #172, 2013). These
principles apply to the whole pipeline, not only to motion:

1. **Physics is the baseline; liberties are dials.** Motion starts physically consistent. Each departure for emphasis
   (hang time, a gravity scale, momentum carried past the physical, impact holds, smears, camera cheats) is a named,
   deterministic, per-beat parameter, measured as a departure. Monty's liberties are an asset. Our version tunes them
   in code, not by feel.
2. **Spend detail where the eye goes.** Monty spent years finding "what the eye will accept as the minimum for a
   believable performance" and warned against detail nobody sees. Weight QA toward what's seen: the face, hands and
   silhouette in the shots used. The perceptual metric, calibrated on Michael's calls (phase 4 item 4), is the tool.
3. **Design for the shot.** Grade from the cameras a sequence uses, not only the turnaround. Per-shot and per-frame
   overrides (pose, line, visibility, shape keys, light) layer over the character without changing it.
4. **Direct control over every automated result.** Monty drew lines as geometry because he distrusted toon shaders
   ("an artist having direct control"). Our outlines are the same trick. Anything a fit or procedure produces must be
   overridable at the finest grain it's used at.
5. **The viewport is the final frame; keep the loop fast.** RWBY rendered from playblasts. We render with EEVEE, and a
   change should reach a picture in minutes (render batching, the boxes).
6. **Stir-fry to explore, bake to merge.** Explore with cheap variants: spec overrides, dial sweeps, contact sheets,
   "shoot wide, cut tight". Gates only guard merges.
7. **A design call is also a rig and motion call.** "If I don't have access to a certain type of rigging, then I simply
   don't design characters that need that rig." The overskirt flaps are an example: separate pieces with their own
   springs.
8. **Stay legible.** Monty's pipeline lived largely in his head, and it caused friction at the studio. Keep ours
   documented (this file, `docs/workstreams/`), gated, and on standard formats in and out (VRM, glTF, BVH). Turn
   Michael's taste calls into calibrated measurements, so the taste is encoded rather than held in one person's head.

The vertical slice, one action beat end to end, is scoped in `docs/SLICE.md`. It starts when the rig is adequate: its
start gate R1–R6.

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
    palette; the rig for eyes. Face depth and hair shape have none since the hull replaced TRELLIS (2026-09-28).
  - **Human review at checkpoints** and for taste calls. Metrics are proxies; Michael's eye is the ground truth.
- **Machine:**
  - The Mac has 16 GB, shared with other sessions. One Clawd build peaks at 2.2 GB of Blender. Build on the build box
    (`charkit remote ...`, above) and keep the laptop at `charkit slots 1`.
  - Agents: the old cap (about 3 at once) was about laptop memory, not agents. Blender and heavy Python ran the 16 GB
    machine out. With builds, fits, gates and renders on the boxes (the build box: 8 slots; the GPU render box, `remote
    --box render`: 3), run as many agents as the work warrants. Keep each agent's local heavy work to the laptop's one
    build slot, and watch the boxes' capacity and the merge coordination (Michael, 2026-09-29). Box capacity isn't a
    hard limit either: slots are a setting (tune them from measured load); more boxes, bigger machines or GPUs are
    provisioning changes that need Michael's approval first.
  - Agents stop at 200 turns. Four of six forks hit it mid-task on 2026-09-29; each resumed fine with a message.
    Brief each fork to commit and report at milestones (about every 100–150 turns) rather than in one long run, and
    to put its state in `docs/workstreams/NAME.md` before long jobs.
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
python -m charkit remote build|tune|gate|run ...              # the same on the build box (see "Remote builds")
python -m charkit tune charkit/spec/clawd.json [--review]   |   python -m charkit triage DIR   |   python -m charkit review serve BUILD
python -m charkit fit charkit/spec/clawd.json --out DIR      |   python -m charkit outfit charkit/spec/clawd.json
python -m charkit history clawd [--check CHECK]              |   python -m charkit ps / slots / wait OUT_DIR
python -m charkit refs-check charkit/spec/clawd.json         |   tools/worktree.sh NAME --profile charkit
for t in charkit/tests/test_*.py; do python $t; done        # the whole suite, about 26 s
```
