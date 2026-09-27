# tools/machinima: decompiled games as a film backend

A decompiled game, rebuilt with a director compiled into it, is a deterministic renderer the film pipeline can drive. The
first backend is **Super Smash Bros. Melee** (NTSC 1.02, [doldecomp/melee](https://github.com/doldecomp/melee)), run in
Dolphin; the first film is `projects/frame-perfect`.

```
choreography (Python, dsl.py) -> script.c -> the decomp's non-matching build (hooks + director.c) -> main.dol
 -> Dolphin, headless: one PNG per game frame, the DSP audio, the game's OSReport log (dolphin.py)
 -> plates between the director's slates, audio cut between its clicks (plates.py)
 -> engine/plate.js composites them on the film clock; report.py checks every hit against the beat grid
```

## Game data: bring your own, never commit it

The repo holds tools and choreography only. The disc image, the extracted disc, the decomp's `orig/` DOL, build outputs and
captured plates all live outside it (`~/games/melee/` by default) or under gitignored paths (`projects/*/assets/plates`).
Use a dump of a disc you own. The right one is Game ID `GALE01`, revision 2, 1,459,978,240 bytes, and its `sys/main.dol`
has the SHA-1 in the decomp's README (`08e0bf20...6bb1a45`).

## Setup (macOS, Apple Silicon)

1. `brew install --cask dolphin`; ninja is already a dependency. Rosetta must be installed.
2. `git clone --depth=1 https://github.com/doldecomp/melee.git ~/games/melee/decomp`
3. wibo's macOS build runs the Metrowerks compilers (the README's wine-crossover cask is gone): download `wibo-macos` from
   decompals/wibo's releases to `~/games/melee/bin/`.
4. `sjiswrap.exe` does not run under wibo-macos (missing kernel32 calls). Instead, transcode the 15 sources that hold Japanese
   text to CP932 once and set `config.shift_jis = False` in `configure.py`. Under a non-Japanese code page the compiler reads
   a Shift-JIS lead byte as a lone character, so a trail byte of 0x5C (a backslash) must be written `\\` inside strings
   (two characters in `mnnamenew.c`). Keep these edits on a local branch.
5. Extract `sys/main.dol` from your disc (`build/tools/dtk vfs cp DISC.iso:sys/main.dol orig/GALE01/sys/main.dol`), run
   `python3 configure.py --wrapper ~/games/melee/bin/wibo-macos && ninja`: the byte-matching build, about 35 s.
6. Extract the whole disc (`dtk vfs cp DISC.iso: ~/games/melee/disc/`). Dolphin boots the folder around `sys/main.dol`, so
   a rebuilt DOL needs no ISO repack.

## Pieces

| File | What it does |
|---|---|
| `dolphin.py` | Runs Dolphin headless in an isolated user folder with pinned settings (single core, DSP HLE, no memory cards, custom RTC, the emulated CPU at 2x), dumps every frame and the audio, stops on a frame count or an OSReport line, collects the log |
| `plates.py` | Trims a capture to the frames between the director's magenta slates (refusing it if the count is off by one), resizes to the display aspect, cuts the game audio between the slate clicks and resamples it to the exact script length |
| `melee/director/` | The director (C89, compiled into the game): boots straight into a VS match, HUD and music off, writes the scripted pads, the camera and the cues every frame, runs closed-loop behaviours, logs hits |
| `melee/build.py` | Compiles a film's choreography, applies the hooks (all `#ifndef MUST_MATCH`, so the same tree still builds the matching DOL), adds the director to the non-matching link, rebuilds, installs the DOL |
| `melee/dsl.py` | The choreography language (below) |
| `melee/report.py` | Matches every intended hit to the logged one: frame error, beat error, misses; `--fix` runs the timing solve, `--calib` records measured frame data, `--hits-js` exports the hits for a composite |
| `melee/timeline.py` | A run as per-fighter action timelines (motion state, start, duration, position) per labelled segment |

## The director

Hooks (inserted by `build.py`):
- **Boot:** straight into the debug VS mode.
- **Match setup:** from `dir_setup` (stage, fighters, costumes, seed).
- **Hits:** fighter hits in `ftColl_8007891C`, item hits (lasers) in `ftColl_80078998`.
- **Laser spawns.**
- **One game frame per rendered image:** the game's loop runs one logic frame per queued pad sample, so a slow render would
  run two logic frames and dump one image. The director build drops the extra samples.

Per game frame it:
- writes `HSD_PadGameStatus` from the script;
- runs the closed-loop behaviours (approach, auto tech);
- drives the debug free camera (eye, interest, fov, roll; keys in world space or tracking the fighters, smoothed, snapping on
  cuts);
- fires cues: freeze (fighters stop, the camera keeps moving), stage visibility, clear colour, reset, set position, facing,
  motion state, percent, marks.

It reports through OSReport, which Dolphin logs from the IPL UART:
- `ATTR` and `LAG`: each fighter's attributes read from the disc;
- `MS s port msid x y`: motion-state changes;
- `HIT s attacker victim dmg move` and `IHIT`;
- `LASER s port x y angle speed`;
- `POS` traces, `MARK`s, and `DIRECTOR END`.

## The choreography language (dsl.py)

`Film(len_s, calib, fix)` is the script clock: frame `s` is film time `s / 60`, and plate frame `s + 1`. Its controls:

| Group | Calls |
|---|---|
| Moves | `port.move(t_hit, name, dir, mark=N)` schedules a move so its hit lands on `t_hit`. With `mark=N` the fighter walks onto the move's range first, closed loop |
| Tech | `waveshine`, `shine_chain(t0, [0, 22], finish='usmash', di_port=)`, `multishine(t, n, every=8 or 15)`, `wavedash`, `jc`, `airdodge`, `di(t_hit, stick)` (the victim crouches first) |
| Auto tech | `auto(t, fastfall, lcancel, lowlaser)` |
| Movement | `approach(t0, t1, range)`, `walk`, `dash`, `shield`, `taunt`, `trace` |
| Camera | `cam(t, eye, at, fov, roll, ease, track)`, `orbit(...)` |
| Cues | `freeze`, `reset`, `percent`, `setpos`, `face`, `mark(t, id, label)` |

## What the labs measured (projects/frame-perfect/director: calib.py, techlab.py, laserlab.py)

**Latency and timing**
- An input on frame `s` takes effect on `s + 1`.
- A-button moves hit 2 frames later than the frame-data tables say; C-stick smashes 1 frame later.
- An aerial's contact frame depends on spacing, so let the timing solve place it.

**Fox and Falco's own numbers, read from the disc**

| | Fox | Falco |
|---|---|---|
| Jumpsquat | 3 | 5 |
| Walk speed | 1.6 | 1.4 |
| Gravity | 0.23 | 0.17 |
| Fast-fall speed | 3.4 | 3.5 |

Both have aerial landing lag of 15 (nair), 22 (fair), 20 (bair) and 18 (up-air, dair). L-cancelled, those halve (15 → 7).

**Wavedash slide by stick angle:** about 21 units at (74, −30), 16 at 45°, 0 straight down, then 10 frames of landing lag.
Angles shallower than about 20° float as a plain air dodge.

**Jumpsquat accepts only rapid jab, grab, up-smash and the short-hop check.** So:
- a multishine presses the next shine on jumpsquat's last frame (an 8-frame cycle);
- a jump-cancelled up-smash out of a shine works.

**Shine jump-cancel:** frame 6 on a hit (its hitlag eats earlier presses; Melee has no buffer), frame 4 on a whiff.
- Air-dodge on jumpsquat's last frame for a wavedash with no airborne frames.
- A waveshine chain cycles in 22 frames hit to hit.

**Waveshines hold only while the victim crouch-cancels and holds down.**
- Fresh shines launch Falco on the second; stale ones (lower damage, lower set knockback) don't.
- Holding B keeps a reflector up, still jump-cancellable: that is how a pillar waits for the opponent to fall back into reach.

**Falco's laser leaves the gun 12 frames after B.**
- Fired before the 7th airborne frame of a short hop, it flies over a standing opponent.
- The laser animation blocks fast fall until it fires.
- Stale-move negation shows in the log (3.0% to 1.8% over repeats).

**Lag.** A capture one frame short of the script is real lag: two logic frames rendered once. The one-frame-per-render hook
fixed it; overclocking the emulated CPU did not, because the render waits on emulated video timing.
