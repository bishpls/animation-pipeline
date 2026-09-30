# Workstream: the perceptual metric (`tool/perceptual`)

The brief: a learned perceptual similarity per view and region against the design, calibrated so it agrees with
Michael's severity calls (the handoff's "Michael's review of the end-to-end run", item 3 "No perceptual weighting", and
phase 4 item 4). It complements the geometric checks. It reads the EEVEE boards, so it runs where boards render (the
GPU render box), never in a gate.

**State: paused 2026-09-29 (the coordinator scaled down concurrency).** Nothing is running on the boxes.

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

## What's built (`charkit/perceptual.py`, uncommitted before this checkpoint; see the commit)

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
  both ways. A region's distance is the coverage-weighted mean, plus p90. Both layer 24 (the metric) and layer 18 are
  stored.
- **Grading** (`grade`) is weight x (distance - floor) against limits from `charkit/refs/clawd/perceptual_calibration.json`,
  which doesn't exist yet: until calibration runs, everything is INFO.
- **Calibration** (`calibrate`): labels in `charkit/refs/clawd/perceptual_labels.json` (17: the brief's 15 plus 2 marked
  `extra` from face.md's checkpoint quotes; 2 praise pairs). The floors are the pool's 10% quantile per (scale, view,
  region). Log-weights per region group (face, hair, accessories, garment, limbs) are fitted with a pairwise logistic
  ranking loss plus a ridge. The WARN and FAIL limits come from balanced accuracy. It reports Spearman's rho unweighted,
  in-sample, LOO (weights and limits refitted without each label), and the geometric checks' own rho, with variants for
  layer 18, no floors, and the brief-only labels. The page is `OUT/index.html`, with each flag's heat map.
- **Output.** `python -m charkit perceptual BUILD` writes `BUILD/perceptual/{perceptual.json, heat_SCALE_VIEW.png,
  dmap_*.npy, legend.png, index.html}`. `--remote` sends the build to the render box, runs it there and fetches the
  result. The CLI is wired in `cli.py`.
- **Not done:** the checkpoint and review page hooks, tests (`charkit/tests/test_perceptual.py`), the calibration run
  itself, the local review page, and the gate.

## Numbers so far (layer 24, before calibration)

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

## Next steps, in order

1. The calibration run on the box. The 26 builds are already staged there in
   `/srv/work/animation-pipeline-perceptual/charkit/out/perceptual_in/<label>/` (boards, bundle, spec, trace,
   qa.json): e2e_ck3, baseline_ck5, confirm_ck7, now, ckpt_full, var_head_neck, var_locks_blunt, var_shade_smooth,
   body2_render, body3_render, code_build, code_now, hull_hair_build, hd_after6, look_base, look_v1, look_v2, look_v4,
   look_v5, l2c_a, face_c, face_g, face_h, face_i, jaw_0, jaw_1. The outfit masks are at
   `charkit/out/clawd/outfit/` in that copy. Sync this worktree first (`CHARKIT_BOX_ENV=infra/gcp/render.env
   infra/gcp/build.sh sync .`).
   - Run in the background, three at a time: `python -m charkit perceptual charkit/out/perceptual_in/X` for each X,
     then `python -m charkit perceptual --calibrate charkit/refs/clawd/perceptual_labels.json --build e2e_ck3=... (one
     per labelled build) --pool ... (all 26) --out charkit/out/perceptual_calibration`.
   - Fetch only `perceptual/` (json, png, npy). The features npz is deleted after use now: an earlier run's 150 MB file
     stalled a fetch through the tunnel.
2. Measure the boots miss before deciding. Try a body grid at 224 px/L (upsampled; about 6.8k tokens, 1-3 s a picture
   on the T4), layer 18, and p90 rather than the mean for small regions. Report every variant tried: n is 17.
3. Write the calibration to `perceptual_calibration.json`, then add the checkpoint and review page hooks (a section
   when `BUILD/perceptual/perceptual.json` exists), and `test_perceptual.py` (registration on a synthetic board, the
   patch matcher, region pooling, fit_limits / LOO on toy data; no model).
4. Build the local HTML page (heat maps over our renders beside the design, the calibration table) and `open` it.
5. The gate: `python -m charkit remote gate tool/perceptual --into pipeline-3d` (it should only add a module and
   tests).
6. The final report: the model and licence, the calibration table with rho, what it catches and misses, and the
   gate-time variant. That variant would run the same features on qa3d.draw's numpy drawings of the bundle, which the
   build box can make. It needs the weights on the build box (the gated download, token from the secret manager) and
   CPU inference: ViT-L at fp32 is about 2-5 s a picture on 32 vCPU.

## Gotchas

- zsh: `"$c:charkit/..."` applies a history modifier. Write `"${c}:..."`.
- `build.sh sync` deletes the copy's `charkit/out/remote/*` except `*.json`. Stage box inputs under
  `charkit/out/perceptual_in/` (excluded from sync, so it isn't deleted) or `/srv/work/...` outside the copy.
- Big transfers go through the bucket (`remote.put`). The object stays there: remove it after (done for
  `remote/stage.tar`).
