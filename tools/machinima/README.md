# tools/machinima: decompiled games as a film backend

A decompiled game, rebuilt with a director compiled into it, is a deterministic renderer the film pipeline can drive. The
first backend is **Super Smash Bros. Melee** (NTSC 1.02, [doldecomp/melee](https://github.com/doldecomp/melee)), run in
Dolphin. The films so far: `projects/frame-perfect` (a 16:9 fight on the beat) and `projects/so-back` (a 9:16 hard edit with
keyed plates, a freeze with a flying camera, the game's own menus, sound and type).

```
choreography (Python, dsl.py) -> script.c -> the decomp's non-matching build (hooks + director.c) -> main.dol
 -> Dolphin, headless: one PNG per game frame, the DSP audio, the game's OSReport log (dolphin.py)
 -> edit-ready plates between the director's slates: portrait or 16:9, keyed pairs, the game audio, the hit list (prep_plates.py)
 -> engine/plate.js composites them on the film clock; report.py checks every hit against the beat grid;
    platesfx.py cuts the game's own sound from each plate at the picture's cue times
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

`build.py` applies every director hook itself (below), so a stock checkout plus the macOS transcode is all the decomp needs:
verified on upstream `64e41ca`, where a fresh build reproduced SO BACK's hits on the same frames as its film capture.
Paths come from `MELEE_DECOMP`, `MELEE_DISC` and `DOLPHIN_USER` (defaults `~/games/melee/decomp`, `~/games/melee/disc`,
`~/games/dolphin-user`); ninja runs with `-j6` (`MELEE_JOBS`).

### Capture lanes: several scenes at once
A capture is mostly emulation time, so scenes can run in parallel. Each lane is a disc folder of its own (its own `sys/`
holding its `main.dol`, with `files/` symlinked to the shared extracted disc, never modified) plus its own Dolphin profile;
run `build.py` with that lane's `MELEE_DISC` and `dolphin.py` with its `DOLPHIN_USER`. `build.py` holds an exclusive lock on
the decomp (`.machinima-build.lock`) from hooking to installing the lane's DOL, so builds serialise (20–30 s each) while
captures run concurrently; Dolphin reads the DOL at boot. SO BACK ran four lanes. Kit changes made while lanes run must be
additive (new cues and methods, never struct layouts or behaviour), because every lane's next build compiles them.

## Pieces

| File | What it does |
|---|---|
| `dolphin.py` | Runs Dolphin headless in an isolated user folder with pinned settings (single core, DSP HLE, no memory cards, custom RTC, the emulated CPU at 2x), dumps every frame and the audio, stops on a frame count or an OSReport line, collects the log |
| `plates.py` | Trims a capture to the frames between the director's magenta slates (refusing it if the count is off by one), resizes to the display aspect, cuts the game audio between the slate clicks and resamples it to the exact script length |
| `prep_plates.py` | Edit-ready plates: 1080x1920 (or 16:9) JPEGs, keyed pairs with an alpha matte, the game audio cut to the plates and an `info.json` with every hit on the frame it is drawn (slate mode); or every frame of a raw folder (raw mode) |
| `vplate.py` | One raw frame to a vertical plate: `aspect` (a 9:16 projection squeezed to portrait), `crop` (a 9:16 slice of 4:3, the HUD undistorted) or `roll` |
| `dmatte.py` | The difference matte of a black pass and a grey-96 pass of the same script: exact coverage, additive glows kept in the black pass |
| `key.py` | A single-pass chroma key with despill, for comparison (it drops glows: prefer `dmatte.py`) |
| `vsheet.py` | A contact sheet of a raw capture at chosen film frames, trimmed and made vertical on the fly |
| `platesfx.py` | A film's game-sound stems: the picture's cue list (`[film t, plate, plate t0, dur, gain, bus, label]`, from `--eval`) cut from each plate's own audio, levelled against the song around it, one stem per bus |
| `melee/ssm.py` | The HAL `.ssm` sound-bank decoder (DSP-ADPCM): every sound on the disc to a WAV (the announcer, SFX, voices) |
| `melee/type/` | Melee's own text from the disc: the word graphics (Game!, Go!, Ready, Success!...), the SIS menu font straight from `main.dol`, the HUD digits and the name plates, with a manifest for `engine/meleetype.js` (its README has the map) |
| `melee/director/` | The director (C89, compiled into the game): boots into a VS match (or one of the game's own modes, driving its menus), HUD and music off (the HUD stays for stock matches), writes the scripted pads, the camera and the cues every frame, runs closed-loop behaviours and CPU players, logs hits |
| `melee/build.py` | Compiles a film's choreography, applies the hooks (all `#ifndef MUST_MATCH`, so the same tree still builds the matching DOL), adds the director to the non-matching link, rebuilds, installs the DOL |
| `melee/dsl.py` | The choreography language (below) |
| `melee/report.py` | Matches every intended hit to the logged one: frame error, beat error, misses; `--fix` runs the timing solve, `--calib` records measured frame data, `--hits-js` exports the hits for a composite |
| `melee/timeline.py` | A run as per-fighter action timelines (motion state, start, duration, position) per labelled segment |

## The director

Hooks (inserted by `build.py`):
- **Boot:** straight into the debug VS mode, or any of the game's own modes (`director_boot`: menu tests also unlock every
  character and stage).
- **Every loop frame:** menu tests write their pads into the master pad status before menus and matches read it
  (`director_boot_frame`); the character select screen reports each port's hand and token positions, so a token can be
  steered to an icon closed loop.
- **Match setup:** from `dir_setup` (stage, fighters, costumes, seed, projection aspect, CPU levels, stocks).
- **Hits:** fighter hits in `ftColl_8007891C`, item hits (lasers) in `ftColl_80078998`.
- **Laser spawns.**
- **One game frame per rendered image:** the game's loop runs one logic frame per queued pad sample, so a slow render would
  run two logic frames and dump one image. The director build drops the extra samples.

Per game frame it:
- writes `HSD_PadGameStatus` from the script;
- runs the closed-loop behaviours (approach, auto tech);
- drives the debug free camera (eye, interest, fov, roll; keys in world space or tracking the fighters, smoothed, snapping on
  cuts);
- fires cues: freeze (fighters stop, the camera keeps moving), stage visibility, clear colour, reset (a clean teleport that
  also restarts the collision sweep), set position, facing, motion state, percent, marks, shield, `glass` (below) and
  `gamecam` (hands the camera back to the game's own match camera, to check what the vanilla game shows).

It reports through OSReport, which Dolphin logs from the IPL UART:
- `ATTR`, `ATTR2` and `LAG`: each fighter's attributes read from the disc (`ATTR2`: air mobility: the ground-to-air
  momentum multiplier, jump h max, air-jump multipliers, air drift and accel);
- `MS s port msid x y`: motion-state changes;
- `HIT s attacker victim dmg move` and `IHIT`;
- `LASER s port x y angle speed`;
- `POS` traces (position, self and knockback velocity, airborne, jumps used, percent), `HB` (every active hitbox while
  tracing), `STATUS`, `MARK`s, and `DIRECTOR END`.

## The choreography language (dsl.py)

`Film(len_s, calib, fix)` is the script clock: frame `s` is film time `s / 60`, and plate frame `s + 1`. Its controls:

| Group | Calls |
|---|---|
| Moves | `port.move(t_hit, name, dir, mark=N)` schedules a move so its hit lands on `t_hit`. With `mark=N` the fighter walks onto the move's range first, closed loop |
| Tech | `waveshine`, `shine_chain(t0, [0, 22], finish='usmash', di_port=)`, `multishine(t, n, every=8 or 15)`, `wavedash`, `jc`, `airdodge`, `di(t_hit, stick)` (the victim crouches first) |
| Auto tech | `auto(t, fastfall, lcancel, lowlaser)` |
| Movement | `approach(t0, t1, range)`, `walk`, `dash`, `shield`, `taunt`, `trace` |
| Camera | `cam(t, eye, at, fov, roll, ease, track)`, `orbit(...)` |
| Cues | `freeze`, `reset` (`fresh=True` also clears the stale-move table, for labs that repeat a move; off by default so a film's staling plays as captured), `percent`, `setpos`, `face`, `mark(t, id, label)`, `status`, `shield`, `cue(t, 'glass' / 'gamecam', a=1)` |
| Setup | `setup(players, stage, seed, entry, aspect=0.5625 (portrait), stocks=N (a stock match: HUD, GAME!, results))`; a player's `cpu=1..9` hands the port to the game's CPU |
| Menus | `Menu(boot='vs')` drives the game's own menus from boot (`hold`, `press`, `goto(f, port, dur, 'falcon')` steers a token to an icon); `Film.menu_hold(boot_frame, port, dur, btn)` holds a button after a match (the victory pose) |

## Capturing for an edit (SO BACK)

**Portrait from the game's own projection.** `setup(aspect=0.5625)` makes the game's camera 9:16. At `--res 4` the dump is
2560x1920 (the portrait view stretched to 4:3), and `vplate.py --mode aspect` squeezes it to 1080x1920: 2.37x supersampled
horizontally, 1:1 vertically, about 0.33 s per frame. A 90-degree camera roll is cheaper but rotates camera-facing effects
(the shine's flash, hit sparks) against the world, which a Melee player sees. Use `crop` (a 9:16 slice of 4:3) only when the
HUD must stay undistorted.

**Keying without a chroma key.** Capture the same script twice with the stage hidden: clear colour black `(0,0,0)`, then grey
`(96,96,96)`. The passes are identical except for the background (the colour gap agrees to 2 levels on 99.99% of pixels).
`dmatte.py` solves the coverage exactly: transmission = (grey − black) / 96 from the channels that didn't clip; the black
pass is the premultiplied colour, additive glows included. Composite `out = black + (1 − a) · BG` (on a canvas: the matte
`destination-out`, then the black pass `lighter`). It keeps the shine's glow, laser streaks and afterimages with no spill; a
green key drops glows and turns lasers yellow, and a green second pass clips under every glow. Never use magenta: it is the
slate colour. On big hits Melee lays a translucent full-frame flash (alpha 0.125, decaying over about 10 frames): over a
bright field it reads as a white wash, so an edit may invert most of it per frame (SO BACK's `dehaze`). Stage-hidden captures
still draw Final Destination's background star sparkles into the matte: clean them for roster-style plates.

**A lost frame without lag.** Captures lost one image deterministically (script frame 7 of every run, 2 of 600 in a long test)
with no pad-queue backlog: two XFB copies landed inside one screen refresh and Dolphin presented only the second.
`dolphin.py` sets `[Hacks] ImmediateXFBEnable`; every capture since has exactly its script's frame count between the slates.
Dumps are now the XFB copy, 640x480 × res with square pixels.

**Frame conventions.** Plate k (1-based) shows the render after logic frame s = k − 1; pads and cues written for s act in
that logic frame. `HIT`, `IHIT` and `LASER` log s + 1 (the counter has already advanced when collisions run), so
`prep_plates.py` records the frame a hit is drawn on and keeps the logged value. `MS` and `POS` are logged at the start of a
frame and report the state after the previous logic frame. Fighters placed at frame 0 are falling and land at script frame
10, and spawn landing lag lasts until about frame 40: leave a lead-in before the first move.

**Freezes and sound.** A director freeze doesn't pause the audio engine: sounds already playing run on and decay, no new
sounds start while frozen, and a frozen move's scripted sounds fire on their own action frame once it resumes (Falcon's
"PUNCH!" on the punch's action frame 50).

**The screen KO's camera.** A top-blast screen KO places the fighter in the view space of `cm_804D6464`, which the game
refreshes only in its standard and fixed camera modes; under the director's free camera the fighter hit the glass of the stale
match-start camera. The `glass` cue writes the director's camera into it. The fighter lands back-first in the vanilla game too:
his rotation is an absolute (0, π, 0), and only his position lives in camera space. Star, screen or plain top KOs are the
game's RNG roll: fix the seed and pick the attempt (SO BACK: attempts 1 and 3 star-KO, attempt 5 screen-KOs, about 33 s in).

**The game's own screens.** A stock match (`stocks=1`) keeps the HUD and ends in the real GAME! splash, then the victory
screen and results. The victory pose is the button held on the winner's port as the screen sets up (`gm_1798.c`): B is pose 0,
Y pose 1, X pose 2, none `HSD_Randi(3)`; hold it with `menu_hold`. The scene load before the victory screen draws no frames but
keeps its audio running, so re-sync that audio where it resumes.

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

## More labs (projects/so-back/director: lab_*.py, SACRED.md)

**Captain Falcon's own numbers, read from the disc (ATTR/ATTR2)**

| walk | dash, run | jumpsquat | full / short hop v | air speed | air accel | gravity | fast fall | weight |
|---|---|---|---|---|---|---|---|---|
| 0.85 | 2.0, 2.3 | 4 | 3.1 / 1.9 | 1.12 | 0.06 at full stick | 0.13 | 3.5 | 104 |

Landing lag: nair 15, fair 19, bair 18, uair 15, dair 24; L-cancelled, the fair lands in 9.

**Carried momentum.** Takeoff speed is min(ground speed × 0.75 + stick × 0.95, 2.1), so even an initial dash hits the cap. A
dash jump leaves at 2.09 and decays 0.01 per frame through the jump (34 frames); on the first frame of Fall,
`ftCo_Fall_Enter` calls `ftCommon_ClampAirDrift` and horizontal speed drops to the air speed (1.12) in one frame. A double
jump resets the speed (1.91 to 1.02), and running off a ledge clamps it at once (2.3 to 1.12). An aerial special started in
the jump keeps the momentum: a dash jump plus an aerial Falcon Punch carries him about 90 units before the hit.

**SHFFL, measured.** Fair on air frame 3, fast fall on the frame after the first descending one (vy −0.05 to −3.5), the
L-cancel pressed below y 6 while descending: 9 frames of LandingAirF, and the dash starts on the first actionable frame.

**Closed-loop tech fails on multi-hit aerials.** The auto fast fall and L-cancel press for 2 frames, and on Jigglypuff's drill
those presses land inside the attacker's hitlag freezes (3 of every 5 frames): script them by hand (fast fall on 75,
L-cancel on 79 in SO BACK's drill).

**Spacing labs.** Marth's forward smash tips only at 32–34 units on a standing Fox (the blade's 14% wins closer; it whiffs past
35) and hits 11 frames after the C-stick; a dashing Fox always eats the blade (his hurtbox leans in), so a tipper punishes a
landing. Falco's laser hits a standing Fox when B goes in on the 8th airborne frame of a short hop (spawn y 14.96). Fox's
Firefox charges for 42 frames (fire hitboxes 20–32) and launches on 43; Falcon's aerial punch hits from action frame 51, so a
punch can land on charge frame 40 with no trade. Pikachu's Thunder comes out on his first actionable frame after an up-throw
and catches a missed tech.

**Taunts face into the stage.** Melee's taunts turn a fighter to face −z, away from the game's own camera: a front-on close-up
sits behind the stage.
