# char3: a new character end to end (tool/char3)

Worktree `~/animation-pipeline-char3`, branch `tool/char3` from pipeline-3d d44db780. The character is **c3**; it is
PRIVATE: its references, prompts, spec, manifest, builds, review pages and report live under `charkit/private/c3/`
(gitignored). This file is public: nothing about the character's identity goes here, only what the pipeline did.

**Goal (Michael, 2026-10-01):** a stress test of how much of charkit is overfit to Clawd. Reference images in, a
rigged model out, no per-character tuning. Steps: (1) a reference set (turnarounds and separated layers), refchecked
and registered; (2) a build from its own spec (base and body declared; no MakeHuman fallback); (3) a generality
report: per stage ran unchanged / generic fix / blocked by a Clawd-specific assumption / missing builder; the QA pass
share with applicable and Clawd-named checks separated; what reached the model; the remaining overfit points ranked.

## Generic fixes (shared code, under tests, gated on the default spec)

1. **Private folders sync to the boxes** (`charkit/bucketsync.py`, `infra/gcp/build.sh`'s rsync fallback):
   `charkit/private/` is gitignored but its files are now in the sync set (git's ignored files under it, listed
   explicitly); a private character's outputs (`charkit/private/<name>/out/`) are not sent and the box never deletes
   them (as `charkit/out`). Tests: `test_bucketsync.py` (3 new; they fail on the old code); the file had no
   `__main__`, so the gate ran none of its tests: fixed.
2. **The implausible-scale guard** (the 68 GB QA hazard, landed generically):
   - `sheetqa.detect_figures` raises when the eye-spacing scale makes the tallest figure under one head length
     (`MIN_FIGURE_L`; the hazard read 0.37 L at 3719 px/L);
   - every measuring grid is capped (`faceqa.MAX_WINDOW_PX`, 100 M pixels, ~65x Clawd's largest) where it is sized:
     `geom.raster.window_shape`, `faceqa.zbuffer_splat`, `bodyqa.crop`.
   Test: `test_sheetqa.test_a_misread_scale_raises_instead_of_sizing_grids_at_it` (the synthetic and Clawd sheets still
   scale; a merged sheet raises; the windows at 3719 px/L raise).

## Step 1: references (in progress)

Same model and tooling as Clawd's (gpt-image-2.5-sunburst, high, 2560x1440, n=2, tools/gptimage.py, every call in
tools/ledger.jsonl with a c3 path). Harness and prompts private (`charkit/private/c3/gen.py`,
`charkit/private/c3/refs/gen/build_prompts.py`). Clawd's body and head turnarounds are attached as the style, layout
and pose reference only.

Order: model sheet (with palette swatches) -> head turnaround -> body turnaround -> 12 layer and breakdown sheets
(base body, head without the crown, the crown alone, the face without the beard, head construction, hair breakdown,
outfit without the drape, the main garment alone, the drape and pin alone, belt and footwear alone, hand breakdown,
garment flat-lay). Calls so far: 15 (n=2 each).

First generality finding (before any build): `sheetqa.detect_figures` fails on c3's turnaround ("no two-eyed figure"):
the colour classes are Clawd's palette (her skin, orange hair, amber irises); c3's skin reads as hair and his irises
are in no class.

## State

- Generic fixes 1-2: done locally, tests pass; not yet committed/gated.
