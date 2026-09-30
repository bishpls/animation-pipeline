# Workstream: the perceptual metric (`tool/perceptual`)

The brief: a learned perceptual similarity per view and region against the design, calibrated so it agrees with
Michael's severity calls (the handoff's "Michael's review of the end-to-end run", item 3 "No perceptual weighting", and
phase 4 item 4). It complements the geometric checks. It reads the EEVEE boards, so it runs where boards render (the
GPU render box), never in a gate.

**State: 2026-09-30, the calibration has run. Verdict: the metric does not track Michael's severities, and doesn't
clearly beat the geometric checks** (primary LOO rho 0.007 against the checks' -0.138; the difference's 90% interval
[-0.16, 0.46] spans 0). So no limits are proposed, `perceptual_calibration.json` isn't written (every grade stays INFO),
and nothing is wired into the preview page. Nothing is running on the boxes. pipeline-3d 9397578 is merged in (92e8fe2).
Review page: `charkit/out/perceptual_calibration/index.html` (the decision, the variants, the "why" numbers, each pair
side by side, each flag's heat map). Every build's pass: `charkit/out/perceptual_runs/NAME/perceptual/` (json, heat maps,
`maps.npz`), from the render box's `charkit/out/perceptual_in/`.

## Results (2026-09-30): read first

Rerun the calibration on the laptop (no model: it reads the fetched passes; about 20 s):

```
R=charkit/out/perceptual_runs; A=(); for b in $(ls $R | grep -v log); do A+=(--pool $R/$b); done
for b in e2e_ck3 ckpt_full body2_render look_v5 face_i body3_render body4b_render body5b_render body6_render jaw_0 jaw_4 jaw_5 eyes2_d; do A+=(--build "${b}=$R/$b"); done
python -m charkit perceptual --calibrate charkit/refs/clawd/perceptual_labels.json "${A[@]}" --out charkit/out/perceptual_calibration
```

32 builds scored (the 26 staged before plus body4b/5b/6_render, jaw_4, jaw_5, eyes2_d), 35 labels, 9 pairs.

| variant | n | rho unweighted | in-sample | **LOO** | geometric blind | geometric now | geometric region | LOO - blind (90%) | AUC raw / LOO / geometric |
|---|---|---|---|---|---|---|---|---|---|
| **primary** (pre-registered) | 35 | -0.003 | 0.024 | **0.007** | -0.138 | -0.059 | -0.208 | 0.15 [-0.16, 0.46] | 0.46 / 0.46 / 0.39 |
| no_floors | 35 | 0.123 | 0.171 | 0.096 | -0.138 | -0.059 | -0.208 | 0.24 [-0.05, 0.53] | 0.47 / 0.44 / 0.39 |
| layer18 | 35 | 0.034 | 0.050 | 0.028 | -0.138 | -0.059 | -0.208 | 0.17 [-0.13, 0.47] | 0.48 / 0.47 / 0.39 |
| layer12 | 35 | 0.072 | 0.121 | 0.107 | -0.138 | -0.059 | -0.208 | 0.24 [-0.07, 0.55] | 0.53 / 0.53 / 0.39 |
| p90 | 35 | -0.102 | -0.094 | -0.104 | -0.138 | -0.059 | -0.208 | 0.04 [-0.29, 0.34] | 0.41 / 0.39 / 0.39 |
| aligned (no neighbour match) | 35 | -0.048 | -0.028 | -0.039 | -0.138 | -0.059 | -0.208 | 0.10 [-0.20, 0.40] | 0.43 / 0.43 / 0.39 |
| body_hi (224 px per L) | 35 | -0.019 | 0.008 | -0.012 | -0.138 | -0.059 | -0.208 | 0.13 [-0.17, 0.43] | 0.46 / 0.46 / 0.39 |
| body_hi_layer12 | 35 | 0.038 | 0.085 | 0.074 | -0.138 | -0.059 | -0.208 | 0.21 [-0.07, 0.49] | 0.48 / 0.47 / 0.39 |
| michael_only | 32 | -0.024 | -0.000 | -0.007 | -0.091 | -0.052 | -0.236 | 0.08 [-0.22, 0.40] | 0.43 / 0.43 / 0.41 |
| no_relative_praise | 28 | 0.123 | 0.108 | 0.082 | -0.087 | -0.355 | -0.313 | 0.17 [-0.26, 0.59] | 0.50 / 0.49 / 0.37 |
| first17 (the old labels) | 17 | -0.362 | -0.244 | -0.333 | -0.549 | -0.549 | -0.466 | 0.22 [-0.25, 0.68] | 0.39 / 0.39 / 0.15 |
| new18 (2026-09-30's) | 18 | -0.010 | 0.028 | 0.028 | 0.150 | 0.593 | 0.305 | -0.12 [-0.58, 0.40] | 0.43 / 0.49 / 0.51 |
| *x_local_top3_l24* | 35 | -0.011 | 0.109 | 0.079 | -0.138 | -0.059 | -0.208 | 0.21 [-0.06, 0.50] | 0.47 / 0.49 / 0.39 |
| *x_local_top3_l12* | 35 | 0.190 | 0.228 | 0.164 | -0.138 | -0.059 | -0.208 | 0.30 [0.03, 0.58] | 0.64 / 0.56 / 0.39 |
| *x_local_top3_l12_hi* | 35 | 0.142 | 0.268 | 0.183 | -0.138 | -0.059 | -0.208 | 0.31 [0.04, 0.60] | 0.71 / 0.65 / 0.39 |

- "geometric blind": the build's own QA on the flagged thing (the QA of the time). "now": the check added after the flag
  to catch it (fitted to the flag, so an upper bound: 0.59 on the new labels). "region": the worst status of every check
  on the region, read mechanically (`geo_region`). AUC: flags of severity 2-3 against praise and mild ones (0.5 chance).
- *x_* (italic): exploratory, added after the primary's numbers were seen: a floor per patch (its 10% quantile over the
  pool: the grids are the same cells on every build) and the mean of the region's 3 worst patches' excess. The best,
  layer 12 at 224 px per L, passes the rule's arithmetic (0.31 ahead, interval above 0) only because the checks' own rho
  is negative; its rho is 0.18 (p 0.29). It isn't eligible (chosen after the fact from 3), but it is the lead for the
  next round (below).
- **Pairs** (primary; raw = distance less floor, worse -> better build). Noise, below, is <= 0.010. Clear agreements:
  bow ckpt_full -> body2 0.157 -> 0.024, pleated skirt body3 -> body4b 0.035 -> 0.008, boots body4b -> body5b 0.007 ->
  -0.009, chin V jaw_0 -> jaw_4 0.041 -> -0.002. Within noise: flaps 0.161 -> 0.155, neck jaw_0 -> jaw_4 0.026 -> 0.035.
  Clear disagreement: the eye structure jaw_0 -> eyes2_d 0.019 -> 0.060 (the profile view). The geometric checks' status
  improved on 1 of 7 (the bow); their value moved the right way on 6 of 7. Implicit midriff body5b -> body6 0.001 ->
  -0.016 (agrees); unreviewed chin jaw_4 -> jaw_5 -0.008 -> -0.009 (within noise).

### Why it doesn't track them (measured; `diagnostics` in calibration.json, the page's "Why" section)

1. **Not registration, not noise.** The board against our z-buffer reads IoU 0.967-0.998 in every view. A region whose
   geometry didn't change moves by a median 0.0006 and at most 0.010 (jaw_4 -> jaw_5, the body regions), 0.0001 / 0.0007
   (body4b -> body5b, the head). The metric is stable; what it measures just isn't what Michael grades. One registration
   caveat: the profile head is anchored on the near iris, and eyes2's turned eye surface moved it 0.004 m (0.017 L, a
   quarter patch; inside the matcher's reach).
2. **The regions dilute local defects.** Twelve of the flags are local (the boots' bridge, the neck column, the midriff
   ledge, jagged hair shading, the band zigzag, the leg bump, the puff spikes, the nick, the pupils, the chin's taper).
   On the region mean they read at the floor, median 0.002, under the noise's 0.010 (body2_boots_front 0.003, r5_midriff
   0.001, look_neck_front 0.002, look_hair_3q -0.001). The body at 224 px per L doesn't change that (boots 0.007 /
   0.011). p90 is worse (LOO -0.10). The local statistic lifts them off the floor (0.06-0.35), but it lifts every region:
   its medians by severity 0: 0.107, 1: 0.094, 2: 0.205, 3: 0.179 (so AUC 0.71, rho still 0.18).
3. **The last layer is contextual: the hair bleeds into the face.** A hair-only change (ckpt_full -> var_locks_blunt,
   the pieces' style only) moves profile hair +0.016, face +0.015, eyes +0.009, neck +0.010 at layer 24; +0.003 / +0.007
   / +0.004 / +0.005 at 18; within 0.002 at 12. Across the pool the hair's distance rank-correlates 0.84-0.89 with the
   face's in every view at layer 24. The heat maps show it: the head's heat is the hair's shape everywhere. Layer 12 is
   the better layer (LOO 0.11 vs 0.01; the neck pair agrees there), but not enough alone.
4. **Severity is relative to the build under review; the metric is absolute.** Praise marks a change from worse, and
   a severe flag is often a local fault in an otherwise design-like region. Raw medians: the old labels, praised 0.041
   against severe 0.035; the new, praised 0.022 against severe 0.014: praised regions read *further* from the design.
   The old labels alone anti-correlate (LOO -0.33): e2e_ck3's praised front face (0.041) reads above most later severe
   flags. The same holds for the geometric checks (-0.55 on the old labels).
5. **The domain gap is 10-30x the signal.** The floors (a drawn design against any render): head hair 0.166, neck
   0.177, accessories 0.214, face 0.104; body flaps 0.150, skirt 0.129, boots 0.058. The flags move a region by 0.00-0.05.

### Recommendation

- Don't wire it as a graded review signal: no limits, grades stay INFO, the preview page unchanged. The geometric
  checks don't rank the severities either (blind -0.14), but the checks added after each flag catch those flags (0.59
  on the new labels): flags as regression tests (decision 2) are doing the work this metric was meant to.
- Keep the module (INFO heat maps on demand, `python -m charkit perceptual BUILD --remote`). What would give it a fair
  second test, in order:
  1. **Pre-register the local statistic** (per-patch floors, layer 12, body at 224 px per L, the region's 3 worst
     patches) and test it on the next review's fresh flags only.
  2. **Pairwise labels.** Michael's before/after calls are the one thing the metric can plausibly track (4 of 7 clearly
     agree, 1 clearly disagrees, against the checks' status 1 of 7). Collect each review as A/B per region, not
     absolute severities.
  3. **Region-anchored flags** (the handoff's review item 7: click the board): a flag's own patches, not its region's
     mean, removes the dilution.
  4. **Tighter regions at layer 12**: the face and eye regions eroded away from the hair edge.
  5. Boards at the design's scale (the body boards are 152 px per L, the sheet 212).

## Calibration run, 2026-09-30: pre-registered before any number was seen

- **Labels** (`charkit/refs/clawd/perceptual_labels.json`): the 17 from before plus 18 from Michael's calls of
  2026-09-30 (the round 4, 5 and 6 body reviews, the jaw and eye reviews; quotes and times from the session): the boots,
  the midriff (rounds 4, 5 and 6), the puff spikes, the leg bump, the flap drape, the band zigzag, the rear tuck, the chin
  taper, the neck notch (`inferred`) and nick (`agent`), the pupils, and four praise labels (the pleated skirt, the boots
  template, the neck and jaw, the eye structure). Each label carries the geometric QA's verdict *of its build's own QA*
  (`check`, the blind comparison) and, where one was added after the flag to catch it, `check_now` (fitted to the flag:
  an upper bound, not a fair comparison).
- **Pairs** (before/after): 7 praise pairs (his before/after calls), 1 implicit, 1 unreviewed; the metric agrees when the
  region's value falls from the worse build to the better one; the geometric check agrees when its status improves.
- **Primary variant, fixed now:** layer 24, floors (the pool's 10% quantile per scale, view and region), the
  coverage-weighted mean, the body at 112 px per L, all labels. Its LOO rho is the headline.
- **Decision rule, fixed now:** the metric "clearly beats" the geometric checks when the primary variant's LOO rho exceeds
  the blind geometric rho by 0.2 or more **and** a paired bootstrap over labels (2000 draws) puts the 90% interval of
  (LOO rho - geometric rho) above 0. Otherwise it doesn't, and the notes say why.
- **Variants, reported whatever they show** (n is ~35, so a variant that wins by a little is noise): no floors, layer 18,
  layer 12, p90 instead of the mean, the neighbour match off (aligned), the body at 224 px per L (`body_hi`), Michael's
  words only (no `inferred` / `agent`), no relative praise.

## The model and its licence

- `facebook/dinov3-vitl16-pretrain-lvd1689m` (DINOv3 ViT-L/16, distilled from the 7B; 4 register tokens; patch 16).
  Hugging Face revision `ea8dc2863c51be0a264bab82070e3e8836b02d51`; `model.safetensors` sha256 `dcb2e451...8179`.
- Licence: the **DINOv3 License** (last updated 2025-08-19; `LICENSE.md` sha256 `25d122eb...904999e`, read from the
  render box's cached snapshot). Section 1.a grants a non-exclusive, worldwide, royalty-free licence to use, reproduce,
  distribute, copy, create derivative works of and modify the materials. There is no non-commercial clause and it is not
  GPL/AGPL. Its limits: 1.b.v trade controls, ITAR, military, weapons, espionage and nuclear uses; 1.b.ii acknowledge it
  in publications; 1.b.i pass the licence on when redistributing the weights (we don't). **Commercial use is allowed,
  so it passes the project rule.** It's the same gated download TRELLIS.2 uses. DINOv2 (Apache-2.0) wasn't needed.
- The weights are gated and cached on the render box (`~/.cache/huggingface/hub/models--facebook--dinov3-vitl16-...`).
  They run in the box's TRELLIS venv (`/srv/work/trellis2/.venv`: torch 2.6 + cu124, transformers 4.57.6), which
  `perceptual.run_features` calls as a subprocess. The charkit venv there has no transformers.
- **float32 only.** In float16 on the T4, DINOv3's patch tokens come out NaN (overflow), and the T4 has no bf16. At fp32
  the model pass takes about 14 s a build (7 views, 14 pictures) including loading.

## What's built (`charkit/perceptual.py`)

- **Registration** (`pairs`), measured per view. Both sides go on one grid with the origin on the eyes (bodyqa's
  convention). The **body** scale is 112 px/L, 32x53 patches: the body sheet's figures against
  `boards/body_{000,035,090,180}`, using the ortho board camera (1.12 H round 0.52 H) and our landmarks. The **head**
  scale is 224 px/L, 28x22 patches, top 0.84 L: head_turnaround's heads against `boards/face_{000,030,090}`
  (perspective, 85 mm at 1 m), each cell's own surface point from our z-buffer's depth projected into the board, so the
  board is rectified to orthographic. Without a bundle, the eye plane stands in (weak perspective).
  - Check on look_v5, the board's figure against our z-buffered figure on the same grid: body 0.975-0.977 IoU, head
    0.974-0.993. Silhouette IoU with the design: body 0.85-0.88, head 0.92-0.95.
  - Cells the face board doesn't reach are cut on both sides. At the head scale, cells where ours is clothed are cut
    too: head_turnaround's heads are bare to the shoulders.
  - The board's figure is its pixels off the flat world colour, at a tolerance of 0.012. The world is 239 239 244 and
    the white boots 243 244 243. A flood fill counted the enclosed background between the legs as figure, so it isn't
    used.
- **Regions.** The design's come from bodyqa classes, the outfit graph's per-view piece masks (the manifest's
  `outfit_masks`: copy `charkit/out/clawd/outfit/` in from `~/animation-pipeline-3d` if it's missing), the QA's face
  region and chin (`refcheck.measure_heads`), eye ellipses, and the star clip grown 0.1 L to take in the crab. Ours
  come from the bundle's objects z-buffered on the grid (`raster.window_zbuffer`). The skin is split by nearest joint
  plus the chin. A region is the union of both sides, grown 3 px; a patch belongs to it at 15% coverage or more. The
  head scale grades face, eyes, hair, neck and accessories; the body scale grades everything else (`PRIMARY`).
- **Distance.** Per patch, 1 - cosine, with each patch matched to its best neighbour within 1 patch on the other side,
  both ways. A region's distance is the coverage-weighted mean, plus p90. Layer 24 (the metric), 18 and 12 are stored
  (`dist_l18`, `p90_l12`, ...), and layer 24 without the neighbour match (`dist_aligned`). `--hi` adds the body at 224 px
  per L (`body_hi`, 64x106 patches, the same window; maps only, no heat pictures). `maps.npz` keeps every pair's
  per-patch maps (each layer, aligned) and each region's patch coverage, so pooling variants (`local_stats`: per-patch
  floors and the worst patches) run on the laptop without the model.
- **Grading** (`grade`) is weight x (distance - floor) against limits from `charkit/refs/clawd/perceptual_calibration.json`,
  which isn't written (the calibration failed its rule): every grade is INFO.
- **Calibration** (`calibrate`): labels in `charkit/refs/clawd/perceptual_labels.json` (35: the brief's 15, 2 from face.md,
  18 from 2026-09-30's reviews; 9 pairs), each with `who`, `relative`, `check` and `check_now`. The floors are the pool's 10% quantile per (scale, view,
  region). Log-weights per region group (face, hair, accessories, garment, limbs) are fitted with a pairwise logistic
  ranking loss plus a ridge. The WARN and FAIL limits come from balanced accuracy. It reports Spearman's rho unweighted,
  in-sample, LOO (weights and limits refitted without each label), the geometric checks' rho three ways (blind, now,
  region), a paired bootstrap of LOO minus blind, AUC, the pairs' agreement (metric and geometric), and `diagnostics`
  (noise, the hair's bleed, the local flags, the era, the floors), over the `VARIANTS`. The page is `OUT/index.html`:
  the decision, the variants, the why, each pair's worse | better heat maps, each flag's heat map.
- **Output.** `python -m charkit perceptual BUILD` writes `BUILD/perceptual/{perceptual.json, heat_SCALE_VIEW.png,
  dmap_*.npy, legend.png, index.html}`. `--remote` sends the build to the render box, runs it there and fetches the
  result. The CLI is wired in `cli.py`.
- **Tests:** `charkit/tests/test_perceptual.py` (11, no model).
- **Not done (on purpose):** the checkpoint and preview page hooks; `perceptual_calibration.json`.

## Numbers from the first box run (2026-09-29, layer 24, before calibration)

look_v5, from the box run (head scale unless noted):

| region | front | three-quarter | profile |
|---|---|---|---|
| face | 0.095 | 0.108 | 0.220 |
| eyes | 0.072 | 0.095 | 0.208 |
| hair | 0.168 | 0.169 | 0.268 |
| neck | 0.161 | 0.249 | 0.259 |
| accessories | 0.214 | 0.234 | 0.324 |
| boots (body) | 0.057 | 0.068 | 0.075 |
| flaps (body) | 0.210 | 0.193 | 0.320 |

body2_render's body scale is close to look_v5's everywhere, because they have the same garments (round 2). For example
boots front is 0.058 and flaps front 0.205.

**First finding: the merged boots don't show.** The boots' region mean is about 0.06, and the heat map is flat at the
feet. At 112 px/L a 16 px patch is 0.14 L, and the bridge between the feet is about one patch. The last layer's
features read "a boot" either way. The profile's face, hair, neck and accessories are clearly the highest distances,
which agrees with Michael's profile calls.

## Next steps (after the 2026-09-30 calibration)

1. Done: the calibration run (above), the 224 px per L body grid (`--hi`, variant `body_hi`), layer 18 and 12, p90, the
   tests (`charkit/tests/test_perceptual.py`: registration on a synthetic board, the matcher, pooling, grading, the fits,
   the local statistic), the local review page.
2. Not done, on purpose (the verdict): `perceptual_calibration.json`, the checkpoint and preview page hooks.
3. If the metric gets its second test (the recommendation's list): stage the next review's builds with `run_all.sh`'s
   pattern (a copy of each build's boards, bundle, spec and trace under the render box's `charkit/out/perceptual_in/`;
   the reviewed builds are usually already in `/srv/work/animation-pipeline-*/charkit/out/` there), add the flags to
   the labels file, and pre-register the local variant as the primary before running.
4. The gate-time variant (qa3d.draw's numpy drawings on the build box, CPU inference) isn't worth building until the
   metric passes a test.

## What the metric needs to read tool/toonrender's boards

The metric reads EEVEE boards now (`boards/body_{000,035,090,180}.png`, `boards/face_{000,030,090}.png`). To read the
new renderer's boards, per board:
1. **The camera, written beside the picture** (a JSON sidecar): orthographic scale and target for the body views,
   lens, sensor, distance and the look-at lift for the head views, the azimuth, the resolution. `Ours.on_grid` hard-codes
   `BODY_BOARD` and `FACE_BOARD` (charkit.scene.boards' values); a sidecar replaces them, and a changed framing then
   can't silently misregister.
2. **A flat background colour distinct from every material** (the figure is its pixels off the background at 0.012:
   EEVEE's world 239 239 244 against the white boots' 243 244 243 is already the tightest case), or better an alpha
   channel.
3. **Depth and object-ID passes** (float depth along the view; an ID per object, or the region name map): the head scale
   rectifies the perspective board on our z-buffered depth of the bundle, and the regions come from z-buffering the
   bundle's objects. The renderer's own passes would make both exact and drop the bundle z-buffer (and its 0.975
   registration IoU).
4. **The same file names and azimuths**, or a `boards.json` index naming them.
5. **Recalibration:** the floors (the drawn-against-rendered gap) and the limits are EEVEE's. A toon renderer changes
   that gap everywhere, so its boards need their own pool and floors; the weights and labels carry over only if a pair
   of the same build rendered both ways shows the per-region distances move together (a check to run once both exist).

## Gotchas

- zsh: `"$c:charkit/..."` applies a history modifier. Write `"${c}:..."`.
- `build.sh sync` deletes the copy's `charkit/out/remote/*` except `*.json`. Stage box inputs under
  `charkit/out/perceptual_in/` (excluded from sync, so it isn't deleted) or `/srv/work/...` outside the copy.
- Big transfers go through the bucket (`remote.put`). The object stays there: remove it after (done for
  `remote/stage.tar`).
- zsh doesn't split an unquoted `$ARGS`: build argument lists as arrays (`A+=(--pool X)`, then `"${A[@]}"`); a string
  gave the calibration zero builds and n = 0 silently.
- The render box's pass is about 100 s a build with `--hi` on the T4 (registration 50 s on its 8 vCPUs under other
  jobs; the model 30-40 s at fp32). On the laptop the registration alone is 13-18 s.
- The labels' `worktree`/`out` paths are only used for each build's `qa/qa.json` (the geometric comparison); the passes
  are read from `--build NAME=DIR`.
