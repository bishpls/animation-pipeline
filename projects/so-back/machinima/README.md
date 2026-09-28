# SO BACK's machinima kit: a pinned fork

**`tools/machinima` is canonical.** This copy is pinned because it is exactly what made the film (the release repo mirrors
it); its improvements have been reconciled into `tools/machinima` (the same director, language and tools, with generic default
paths). Start new work there.

This is a copy of the director kit from the **geno** branch (`~/animation-pipeline-geno`, commit `a93283a`), pinned so SO
BACK builds don't move under a parallel session. It covers `tools/machinima/melee/{build.py,dsl.py,report.py,timeline.py,director/}`
and `tools/machinima/{dolphin.py,plates.py}`. Reconcile it into `tools/machinima` once both branches land.

Differences from the geno copy:
- **Paths.** `build.py` defaults to our own decomp worktree, `~/games/melee/decomp-soback` (branch `soback`, from the decomp's
  `ext` at `fcb0322`), and our own vanilla disc, `~/games/melee/disc-soback` (freshly extracted from the ISO: no Geno files,
  no modded banks). `ROOT` is the repo root, and ninja runs with `-j6` (`MELEE_JOBS`).
- **Profile.** `dolphin.py` defaults to our own profile, `~/games/melee/dolphin-soback`.
- **Immediate XFB.** `dolphin.py` sets `[Hacks] ImmediateXFBEnable = True`. Without it, this build lost images
  deterministically: script frame 7 after the slate on every run, and 2 frames of a 600-frame test. The loop never had a
  pad-queue backlog, so this isn't lag. On VI timing, two XFB copies landed inside one VI, and the first was never
  presented; duplicate-present skipping hid the repeat. With it on, every capture has exactly `len` frames between the
  slates. It also changes the dump size: dumps are the XFB copy, 640x480 x res (square pixels), not 640x528 x res.

New files:
- `vplate.py`: vertical 1080x1920 plates from a capture (`--mode aspect|crop|roll`).
- `dmatte.py`: a difference matte from a black pass and a grey-96 pass of the same script.
- `key.py`: a single-pass chroma key with despill, for comparison.

## Vertical plates: `aspect = 9/16` at `--res 4`
`f.setup(..., aspect=0.5625)` makes the game's projection portrait. The 2560x1920 dump is the 9:16 view stretched to 4:3,
so `vplate.py --mode aspect` squeezes it to 1080x1920. That is 2.37x supersampled horizontally and 1:1 vertically, at
about 0.33 s per frame (a 30 s film at 60 fps is about 10 min per pass).

The other two methods:
- **crop** (a centred 9:16 crop of 4:3): the same pixels vertically, and identical content. Use it only when the HUD
  must stay undistorted.
- **roll** (a 90° camera roll, rotated back, at `--res 3`, about 0.22 s per frame): rotates screen-aligned billboards
  90° against the world (the shine's opening flash), and shifts hit sparks. An expert would see it. Don't use it.

## Keying: two deterministic passes
Build the same script twice, with the stage hidden and the clear colour black (`0,0,0`), then grey (`96,96,96`), and
capture both. The pair is bit-identical except for the background (measured R/B drift: 0). `dmatte.py` solves the
coverage exactly: transmission = (grey pass − black pass) / 96, from the channels that didn't clip. The black pass is
the premultiplied colour, with additive glows included.

Composite as `out = black + (1 − a) · BG`. On a canvas, draw the matte with `destination-out`, then the black pass with
`lighter`.

Compared with a chroma key, this keeps:
- the shine's glow;
- Phantasm afterimages;
- laser streaks, which turn yellow over a green key;

and it has no spill or fringe. A green second pass clips under every glow, which shows as a grey haze. Some Melee glows
are alpha-blended rather than additive, so over a very bright background they read as a pale haze. That is correct, but
choose backgrounds with that in mind.

If only one pass is affordable, key on green `(0,255,0)` for most of the cast. Key on blue `(0,0,255)` for the green
costumes: Link, Young Link, Luigi, Yoshi and Bowser. Never use magenta `(255,0,255)`: it is the slate colour, and
`plates.py` would read it as a slate.

## Commands
```bash
# script: projects/so-back/director/NAME.py (a dsl Film); env vars pick variants
.venv/bin/python projects/so-back/machinima/melee/build.py projects/so-back NAME                 # -> ~/games/melee/disc-soback/sys/main.dol
.venv/bin/python projects/so-back/machinima/dolphin.py run ~/games/melee/disc-soback/sys/main.dol ~/games/melee/plates/soback_NAME \
    --until 'DIRECTOR END' --res 4 --timeout 1800
.venv/bin/python projects/so-back/machinima/plates.py trim ~/games/melee/plates/soback_NAME OUT --len FRAMES --aspect 4:3 --w 2560  # count check + game.wav
.venv/bin/python projects/so-back/machinima/vplate.py RAW.png OUT.png --mode aspect
.venv/bin/python projects/so-back/machinima/dmatte.py BLACK.png GREY.png OUT_PREFIX                 # after vplate on both
```

## Frame conventions (measured on the sacred combo)
Plate k (1-based) shows the render after logic frame s = k − 1. Pads and cues written for s act in logic frame s, so they
show on plate s + 1.
- **Logged one frame late:** `HIT`, `IHIT` and `LASER` log s + 1, because the director's counter has already advanced
  when collisions run. The knee logged at 64 is drawn on script frame 63.
- **One frame behind:** `MS` and `POS` are logged at the start of a frame. They report the state after the previous
  logic frame.
`deliver.py` converts `HIT` lines to the frame they are drawn on.

## Freezes and sound
A director freeze (`DIR_FREEZE`) doesn't pause the audio engine:
- Sounds already playing run on and decay naturally.
- No new sounds start while frozen.
- A frozen move's scripted sounds fire on their own action frame once it resumes: Falcon's "PUNCH!" at the punch's
  action frame 50, two frames before the hit.
