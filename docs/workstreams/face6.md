# Workstream: face round 6, Michael's face flags (`tool/face6`)

Worktree `~/animation-pipeline-face6` (sparse), branch `tool/face6` from pipeline-3d 004efc3. Michael's review of the
build (2026-09-30 evening, preview 1580f95):
1. the iris doesn't fit (larger than the opening, past the sclera; the design's iris top and bottom sit on the lid lines);
2. the lash detail is lost (a solid block; the design's upper lash line has spikes, flicks, separation);
3. the brows' shape and thickness are a little off;
4. the default smile is quite off-model;
5. the mouth seems misplaced in three-quarter;
6. in profile the mouth reads higher than the reference;
7. the nose is invisible from the front and three-quarter (the design draws a small nose mark).

Nothing measured any of them (eye_iris_ratio is a width ratio; no lash, brow, smile, mouth-placement or front/3q nose
check). Order: measure each flag as a calibrated check, then fix cheapest-visible first, reporting the face pieces' shape
IoU per view beside every check moved.

## State

- Step 1 (measurement): `charkit/faceflags.py`, the QA part `face_flags` (order 850). Lab scripts under
  `charkit/out/face6/` (lab1-6).
