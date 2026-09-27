# FRAME PERFECT: making-of

▶ **[Watch it](https://github.com/bishpls/animation-pipeline/releases/tag/frame-perfect-v1.0)**: 34 s, 1080p60 (the master and a
14 Mbps cut for posting).

A 34-second Melee fight in which every hit lands on the beat, because every input was written as code on the song's beat
grid. Fox and Falco on Final Destination: a cold open, fourteen bars of combos cut on the downbeats, a freeze on the song's
dead stop, and a star KO on the ring-out.

**No player touched a controller, and no video model made a frame.** The fight is Super Smash Bros. Melee itself. It runs from
a disc dump the project's human owns, rebuilt from the [doldecomp/melee](https://github.com/doldecomp/melee) decompilation
with a director compiled into the game, and captured in Dolphin one image per game frame. The engine composites the title,
a small frame-and-beat readout and the end card. *Unofficial, non-commercial fan work.*

## How it works

```
choreography.py ──> director tables (C) ──> Melee, rebuilt from the decomp ──> Dolphin, headless
      ^                                                                              │
      └──── report: did each hit land, on which frame? (the game's own hit log) <────┤
                                                                                     v
                         plates (one PNG per game frame) + the game's sound ──> engine composite ──> mp4
```

- **The director** is about 530 lines of C inside the game. It:
  - boots straight into the match, with the HUD and music off;
  - writes each fighter's controller state every frame, and flies a free camera, keyed or tracking the fighters;
  - freezes the fighters while the camera keeps moving;
  - reports every hit, laser and action-state change back through the game's debug log.

  It is hooked in with `#ifndef MUST_MATCH`, so the same source tree still builds the byte-identical original.
- **The choreography** is Python on the song's clock. `fox.move(6.0, 'shine')` means "the shine's hitbox touches Falco at
  6.000 s". A beat is exactly 30 game frames at 120 BPM, and each move carries its measured startup, so the input goes in at
  the right frame.
- **The loop closes on evidence.** After each run, `report.py` matches every intended hit to the one the game logged, and the
  timing solve shifts any hit that landed a frame off. The final cut has 28 of 28 hits on their exact frame.
- **Tooling:** everything is in [`tools/machinima/`](../../tools/machinima/README.md), with setup, the director's controls and
  the full list of measurements.

## Choreography: trading bars

Melee won't let two fighters trade a hit on every beat, because whoever was just hit is in hitstun. So they trade bars like a
dance battle: each bar is one fighter's combo, and the next bar cuts to the other's turn.

- **Fox's waveshine:** shine, jump out of it on frame 6, wavedash in with no airborne frames, shine again, then a
  jump-cancelled up-smash.
- **Falco's pillar:** short-hop dair, L-cancelled; a held shine that pops Fox up; jump-cancel; a second dair as Fox falls back
  into reach.
- **Short-hop aerials:** fast-fallen and L-cancelled by a reflex inside the director, not by the script.
- **Falco's short-hop laser:** fired on the 8th airborne frame, low enough to hit.
- **Fox multishining** on the eighths while Falco walks in; the seventh shine connects.
- **Falco's up-tilt, up-tilt, up-air juggle** and **Fox's up-throw into up-air** at 50%.
- **The finisher:** an up-smash at 150% on the last downbeat. The music stops dead, the world freezes with it, and the camera
  orbits the suspended Falco until the re-entry hit.

Fighters hit their marks with a closed-loop "approach" run inside the game: walk toward the opponent until the move's measured
range, then stand. Victims crouch into shines and hold down through the hitlag (crouch cancel and DI), which is what keeps a
waveshine on the floor.

## What the labs taught us

Before choreographing anything, lab scripts measured the game. The same director ran calibration grids, and the numbers
came from the game's own log.

- **The game's own attributes.** Read from the disc's fighter data: Fox's jumpsquat is 3 frames and Falco's 5; their weights
  are 75 and 80; aerial landing lag is 15 to 22 frames, halved by L-cancelling.
- **Wavedash slide by stick angle.** About 21 units at a low angle, 16 at 45°, 0 straight down. Anything shallower than about
  20° floats as a plain air dodge.
- **Jumpsquat accepts only up-smash, grab and rapid jab**, so a multishine has to press the next shine on jumpsquat's last
  frame, an 8-frame cycle.
- **A shine's hitlag eats a jump press**, and Melee has no input buffer, so a waveshine jumps on frame 6 on a hit, not 4.
- **Fresh shines launch Falco on the second hit; stale ones don't.** The lab's chains held because dozens of shines had
  staled the move, so the film's chains are two shines long.
- **Falco's laser leaves the gun 12 frames after B.** Before the 7th airborne frame it flies over a standing Fox, which is the
  lesson every Falco player learns. The logged spawn heights run from 20.7 units (misses) down to 5.8 (hits).
- **A capture one frame short of the script is real lag**: two game frames, one image. A director build now runs one game
  frame per rendered image.

## Who did what

- **Michael Bishop (human):**
  - Chose Melee and supplied his own disc dump.
  - Directed from Melee expertise: asked for combos, not traded hits; wavedashes, L-cancels, DI and jump-cancelled shines;
    percent as the knockback knob.
  - Spotted the waveshines running slow, the short-hop-laser height problem, and the fighters overlapping at the end of the
    walk-in.
- **Claude (Opus 5.5, Claude Code):**
  - Research, the Mac build, the director, the choreography language and the labs.
  - The choreography and camera, the composite, the mix, and this document.
- **Third parties:**
  - The doldecomp/melee contributors (the decompilation); Dolphin (the emulator); decompals' wibo and encounter's dtk (the
    Mac toolchain).
  - ElevenLabs Music v2.5 (the song: 4 takes, one rejected for drifting off the 120 BPM grid).
  - Gemini (three blind, shuffled rankings of the takes; it invented an impact at 24 s that isn't in the song, so the
    structure was measured instead).
  - No image or video models.

## Numbers

- **Wall time:** about 2 h 45 min from the first install to the first full cut.
- **Runs:** about 30 director builds and runs, each 1–2 minutes at low resolution; the final capture was about 6 minutes at
  3× internal resolution.
- **Hits:** 28 scripted, 28 on their exact frame.
- **Code:** about 1,570 lines across the director, the language, the build glue, the runner, the plate tools and the film's
  choreography.
- **Paid calls:**
  - ElevenLabs: 4 music takes, 136 s of audio (logged in `tools/ledger.jsonl`).
  - Gemini: 3 ranking calls (`gemini.py` doesn't log to the ledger yet).
- **Sync:** the game's hit sound leads the song's kick by about 24 ms and the visible impact trails it by up to 17 ms, because
  Melee starts a hit's sound on the collision frame and draws the spark a frame later. Both are inside the ±45 ms window
  people perceive as together.

## Game data

The repo holds tools, choreography and the composite, and never any game data. The disc image, the extracted disc, the
decomp's copy of the game's executable, builds and captured plates all live outside it. To reproduce the film, dump your own
disc (see `tools/machinima/README.md`) and run:

```bash
.venv/bin/python tools/machinima/melee/build.py projects/frame-perfect           # choreography -> director -> main.dol
.venv/bin/python tools/machinima/dolphin.py run ~/games/melee/disc/sys/main.dol ~/games/melee/plates/fp_cap --until 'DIRECTOR END' --res 3
.venv/bin/python tools/machinima/plates.py trim ~/games/melee/plates/fp_cap ~/games/melee/plates/frame-perfect --len 2040 --aspect 16:9 --w 1920
ln -sfn ~/games/melee/plates/frame-perfect projects/frame-perfect/assets/plates && bash projects/frame-perfect/mix.sh
node engine/render.mjs projects/frame-perfect --frames --workers=6 --fps=60 && node engine/render.mjs projects/frame-perfect --encode --fps=60 --audio=projects/frame-perfect/assets/mix.wav
```

This is a non-commercial fan video, the kind Nintendo's Game Content Guidelines are written to allow; read them before
monetizing or redistributing anything.
