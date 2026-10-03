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
| `dolphin.py` | Runs Dolphin headless in an isolated user folder with pinned settings (single core, DSP HLE, no memory cards, custom RTC, the emulated CPU at 2x, immediate XFB), dumps every frame and the audio, stops on a frame count or an OSReport line, collects the log. `--logonly` writes only the log and runs unthrottled (labs read from the log); `--audioonly` dumps audio without frames; `--cpu X` / `--nooverclock` set the emulated clock for lag measurement; `DOLPHIN_SLOTS=N` waits for one of N machine-wide slots |
| `plates.py` | Trims a capture to the frames between the director's magenta slates (refusing it if the count is off by one), resizes to the display aspect, cuts the game audio between the slate clicks and resamples it to the exact script length |
| `prep_plates.py` | Edit-ready plates: 1080x1920 (or 16:9) JPEGs, keyed pairs with an alpha matte, the game audio cut to the plates and an `info.json` with every hit on the frame it is drawn (slate mode); or every frame of a raw folder (raw mode) |
| `vplate.py` | One raw frame to a vertical plate: `aspect` (a 9:16 projection squeezed to portrait), `crop` (a 9:16 slice of 4:3, the HUD undistorted) or `roll` |
| `dmatte.py` | The difference matte of a black pass and a grey-96 pass of the same script: exact coverage, additive glows kept in the black pass |
| `key.py` | A single-pass chroma key with despill, for comparison (it drops glows: prefer `dmatte.py`) |
| `vsheet.py` | A contact sheet of a raw capture at chosen film frames, trimmed and made vertical on the fly |
| `platesfx.py` | A film's game-sound stems: the picture's cue list (`[film t, plate, plate t0, dur, gain, bus, label]`, from `--eval`) cut from each plate's own audio, levelled against the song around it, one stem per bus |
| `melee/ssm.py` | The HAL `.ssm` sound-bank decoder (DSP-ADPCM): every sound on the disc to a WAV (the announcer, SFX, voices) |
| `melee/type/` | Melee's own text from the disc: the word graphics (Game!, Go!, Ready, Success!...), the SIS menu font straight from `main.dol`, the HUD digits and the name plates, with a manifest for `engine/meleetype.js` (its README has the map) |
| `melee/director/` | The director (C89, compiled into the game): boots into a VS match (or one of the game's own modes, driving its menus), HUD and music off (the HUD stays for stock matches), writes the scripted pads, the camera and the cues every frame, runs closed-loop behaviours and CPU players, logs hits. `dir_results_music = 1` (a lab's choice; films emit 0) turns the music back on when the scene leaves the match, so the results screen's victory fanfare plays |
| `melee/build.py` | Compiles a film's choreography, applies the hooks (all `#ifndef MUST_MATCH`, so the same tree still builds the matching DOL), adds the director to the non-matching link, rebuilds, installs the DOL |
| `melee/dsl.py` | The choreography language (below) |
| `melee/report.py` | Matches every intended hit to the logged one: frame error, beat error, misses; `--fix` runs the timing solve, `--calib` records measured frame data, `--hits-js` exports the hits for a composite |
| `melee/timeline.py` | A run as per-fighter action timelines (motion state, start, duration, position) per labelled segment |
| `melee/audio/hps.py` | Reads and writes Melee's HALPST music streams (`files/audio/*.hps`): DSP-ADPCM stereo in 0x10000-byte blocks, each block carrying the decoder state at its start; the last block's next pointer ends the stream or loops it. `check` proves a file against vgmstream and a re-encode. The game opens streams by path through the disc's file table, so a new `.hps` in an extracted disc's `files/audio/` is found by name |

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
  run two logic frames and dump one image. The director build drops the extra samples. The same test is the lag measure:
  the director logs `LAGFRAME s n` before the flush (one block, one hook: `build.py`'s `PAD_LAG`, with `GMSCENE_UPGRADES`
  collapsing older plain blocks, and a check that exactly one lag call is in `gmscene.c`).
- **Agent worktrees build only into a sandbox:** from `animation-pipeline-<name>` (other than the `geno` integration
  checkout) `build.py` refuses to run unless `MELEE_DECOMP` and `MELEE_DISC` are set (`melee/sandbox.sh NAME`).

Per game frame it:
- writes `HSD_PadGameStatus` from the script;
- runs the closed-loop behaviours (approach, auto tech);
- drives the debug free camera (eye, interest, fov, roll; keys in world space or tracking the fighters, smoothed, snapping on
  cuts);
- fires cues: freeze (fighters stop, the camera keeps moving), stage visibility, clear colour, reset (a clean teleport that
  also restarts the collision sweep), set position, facing, motion state, percent, marks, shield, `glass` (below) and
  `gamecam` (hands the camera back to the game's own match camera, to check what the vanilla game shows; the director logs
  `CAM` lines while the game's camera runs, as it does for `Film.game_camera()`), and the labs' `feet`, `shieldhp`, `item`,
  `sfx`, `anim`, `grdump`, `items`, `shoot`, `stall` and `perf`. Cue numbers: 1-25 Geno's labs, 40-41 SO BACK's lanes,
  50 on the Geno trailer (`director.h`, `dsl.py`'s `CUE`).

It reports through OSReport, which Dolphin logs from the IPL UART:
- `ATTR`, `ATTR2` and `LAG`: each fighter's attributes read from the disc (`ATTR2`: air mobility: the ground-to-air
  momentum multiplier, jump h max, air-jump multipliers, air drift and accel);
- `MS s port msid x y`: motion-state changes;
- `HIT s attacker victim dmg move` and `IHIT`;
- `LASER s port x y angle speed`;
- `POS s port x y motion hipx hipy vx vy kbx kby air jumps percent` traces (the hip joint's world position, Geno's labs; then
  self and knockback velocity, airborne, jumps used and percent, SO BACK's), `HB` (every active hitbox while tracing),
  `STATUS`, `MARK`s, and `DIRECTOR END`. Fields only append, so a parser reading by index keeps working.

## The choreography language (dsl.py)

`Film(len_s, calib, fix)` is the script clock: frame `s` is film time `s / 60`, and plate frame `s + 1`. Its controls:

| Group | Calls |
|---|---|
| Moves | `port.move(t_hit, name, dir, mark=N)` schedules a move so its hit lands on `t_hit`. With `mark=N` the fighter walks onto the move's range first, closed loop |
| Tech | `waveshine`, `shine_chain(t0, [0, 22], finish='usmash', di_port=)`, `multishine(t, n, every=8 or 15)`, `wavedash`, `jc`, `airdodge`, `di(t_hit, stick)` (the victim crouches first) |
| Auto tech | `auto(t, fastfall, lcancel, lowlaser)` |
| Movement | `approach(t0, t1, range)`, `walk`, `dash`, `shield`, `taunt`, `trace` |
| Camera | `cam(t, eye, at, fov, roll, ease, track)`, `orbit(...)` |
| Cues | `freeze`, `reset` (clears the stale-move table by default on the Geno line, as every Geno lab was measured; `fresh=False` keeps the game's staling, as main's films were captured: FRAME PERFECT's damage), `percent`, `setpos`, `face`, `mark(t, id, label)`, `status`, `shield`, `cue(t, 'glass' / 'gamecam', a=1)` |
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
SO BACK's dumps were then the XFB copy, 640x480 × res with square pixels. On the Geno line (its decomp, a 4:3 capture at
`--res 2`) the dump stays 1280x1056 with the hack on or off, and every frame but the lost one is pixel-identical: an A/B of
one DOL (2026-09-30) gave 359 frames between the slates without it, the image after script frame 7 missing, and 360 with
it. Geno's boards that assume 1280x1056 at res 2 still hold.

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

## New fighters and menus (datkit, projects/geno)

`melee/datkit.sh` runs a small C# tool over HSDRaw (Ploaj/HSDLib, vendored at `vendor/HSDLib`, .NET 8 SDK): `roots`,
`tree`, `jobjs`, `skel`, `rest`, `actions`, `figa`, `parts`, `lookups`, `texdump`, `animkeys`, `mscan`, `mdump` and
`mframes` inspect Melee's .dat files; `fighter-build`, `css-geno` and `menus-geno` write them. Outputs derived from the
disc stay in `$MELEE_WORK` (`~/games/melee/work`).
- **Menus key a character by frame.** Portraits, emblems, stock icons and name images are texture animations whose frame is
  the character's index (CSS: hud + costume * 30; results screen and HUD: gm_80168B34, 180 + costume for Geno; VS Records:
  SELKIND). A new character appends an image and keys its frame (and the frame after, back to what it showed).
  `projects/geno/menus/build.py` builds all four menu files (character select, results, VS Records, HUD) into
  `$MELEE_WORK/menus/out` with review sheets and an install script; `mscan` lists every texture animation in a file.
- **Re-saved files need their GPU buffers flagged.** HSDRaw writes blocks of 0x40 bytes or less on 4-byte boundaries unless
  flagged, so after any size change small palettes, tiny images and short display lists land off the GPU's 32-byte grid.
  css-geno and menus-geno flag every model's buffers before saving (`TexKit.AlignGX`); `projects/geno/menus/gxalign.py`
  checks a file.
- **A fighter is three files.** `PlXxNr.dat` is the model (a joint tree with inverse binds and the meshes on the root),
  `PlXxAJ.dat` the animations (one figatree archive per animation, 0x20-aligned), and `PlXx.dat` the fighter data
  (attributes, a 303-entry action table naming each animation's offset and size, move scripts, hurtboxes, engine bones,
  IK, hand-pose model parts (anims.json `part_poses`), visibility lookups). `fighter-build` assembles all three from a rig and an animation set
  (`projects/geno/rig/rig.py`, `anims.py`); a template supplies what the rig doesn't author yet.
- **A costume from a glTF** (`GltfModel.cs`): with `"model": {"high": ..., "low": ..., "eyes": [...]}` in rig.json,
  fighter-build keeps the rig's skeleton and takes the meshes from Blender: joints matched by name (`J%02d` through
  rig.json `jnames`), vertices re-bound to the rig's rest pose by their joints' positions, one DObj per primitive with
  Mario's material setup, glTF's counter-clockwise faces reversed for GX with the cast's cull bit, textures CMP (eyes CI8),
  eye frames as texture animations plus the material lookup the scripts' eye commands index, the metal model as one
  reflection-mapped copy per cull mode (the engine holds 32 metal DObjs, 124 costume DObjs), every GPU buffer aligned.
  `gltf-model` builds just the costume file; `art/gltf_compare.py` checks a round trip through `export`.
- **Joint indices are depth-first positions** in the joint tree (ftParts_SetupParts, figatree nodes, part-pose trees and
  the metal model's joints all walk it that way), so a joint added under the neck or head renumbers everything after it.
  That is safe while everything is generated from rig.py by name (rig.json, anims.json, moves.py's parts, the C parts
  table `ftgeno_rig.inc`, which must be regenerated and the game rebuilt: its joint count must match the model's).
- **The skeleton contract is the parts table**, not joint indices: about 54 engine parts (TopN, TransN, XRotN, YRotN,
  HipN, the legs, arms, fingers, NeckN, HeadN, ThrowN, TransN2) mapped per kind (PlCo.dat, or C for a new kind). The engine
  retargets between kinds through it (thrown victims, for one). Keep Melee's local conventions: a T-pose facing +Z, each
  limb chain running down its bones' local X.
- **Vertices bound to one bone are stored in that bone's frame;** only multi-weight envelopes use world positions.
- **Action flags' low 6 bits are the authored kind.** Author a new kind's animations with its own id, or they retarget
  rotation-only and the model collapses.
- **The OnDeath callback must switch the body model on** (`ftParts_80074A4C(gobj, 0, 0)`), or every mesh stays hidden.
- **Costume textures:** scripts drive eye-blink texture animations by index; a model without them needs the guard in
  `ftAnim_80070458` (non-matching builds only), or the game asserts "texture no exist!".
- **HSDRaw gotchas:** accessors are fresh wrappers on every read (compare `_s`, not objects), and array properties such as
  an action table's `Commands` return copies (edit, then assign back).
- **Kirby's copy of a new kind** (Geno: decomp `ftKirby/ftkirbyspecialgeno.c`): Kirby's per-kind tables stop at 0x20,
  so each gets rows for 0x21 and the new kind: the hat load/unload pairs (`ftKb_Init_803C9CC8`, indexed `kind * 2`), the
  ground and air neutral-B entries (`ftKb_Init_803C9DD0`, `ftKb_Init_803C9E54`), and the hat file, costume and effect
  rows (already `Ft_Kind_Max`-sized). The copy's states go before `ftKb_MS_Count`, and the copy-move range in
  `ftKb_SpecialN_800F5C34` reads to it. `ftCo_800BD9E0` decides what a swallow copies. A hat archive lands in
  `((KirbyHatStruct**) &ft_80459B88)[kind]`: the decomp's `hats[k]` names are one kind off. Kirby plays copies on his
  own actions (PlKb.dat), so a new copy borrows the nearest vanilla copy's and retimes them with the animation rate.
- **Menu tests:** a `Menu` script (dsl.py) boots into a game mode (`boot='vs'`), unlocks the roster, writes pads into the
  master status and steers CSS tokens closed-loop (`goto`), so the real menus can be driven and checked.
- **Move scripts** are assembled in Python (`projects/geno/rig/fcmd.py`) with the decomp's own layouts (HSDRaw's table
  differs: the hitbox's first word, the smash charge's size). `at(n)` then a hitbox means active from frame n (1-based
  frame data); hitboxes address engine parts through the common-bone flag, so scripts never depend on joint order.
- **Animations must not key the engine's joints:** TopN carries the facing (key it and the fighter faces the camera),
  TransN2 is the origin, and the JA joints hold each limb's rest frame.
- **A character's own states** read `cmd_vars[0]` for "interruptible" (fcmd `interruptible()`); `allow_interrupt` is the
  common attacks' flag and survives into a new state, which interrupts a special on its first frame.
- **Labs:** `projects/geno/director/normals_lab.py` and `specials_lab.py` run every move against a standing Fox with
  resets between tries (after the entry: a reset needs ground under the fighter), `labs/report_normals.py` turns the hit
  log into measured frame data, and `setup(coll=1)` turns on the developer hitbox and hurtbox display.

### Items (a new fighter's projectiles)

- **New item kinds go after the last one** (`It_Kind_Kyasarin_Egg`), with their own article, logic and render tables
  (`decomp src/melee/it/kinds/itgeno.c`); every place that picks a table by kind range gets one more branch (`item.c`
  article/logic lookup, render link and hold kind; `itmaplib.c` collision class). Inserting into the character range
  would shift the stage and Pokémon kinds that data files reference by number. The character-article pointer array is
  loaded from the item file at a fixed size, so new kinds can't write past it.
- **Articles are data in the fighter's own file** (`ftData+0x48`): common attributes, special attributes (a float
  block the item code reads), per-state scripts, a model. `datkit fighter-build` copies them from donor fighters and
  overrides attributes, scripts and states (`projects/geno/rig/articles.py`); `datkit articles` dumps any fighter's.
- **Item scripts are their own command set** (`it_803F22A8`, from 0x0A): create-hitbox is six words (the fighter's five
  plus a word whose top byte is the **re-hit interval**, frames before a victim can be hit again, 0 = once; Falco's laser
  uses 16), 0x0C sets a hitbox's damage, 0x0E removes one, 0x0F clears all. Word 4's last two bits are hit-grounded and
  hit-aerial (aerial-only meteors, grounded-only pop-ups). `fcmd.ItemScript` encodes them.
- **Item scripts run on the item's animation clock:** a wait longer than the state's animation never ends. Drive timed
  behaviour (multi-hits, growth) in the item's code instead: clear a live hitbox's victims to re-hit (`it_8026FCF8`), set
  its radius (`hit->scale` then `it_80275594`) or damage (`it_80272460`).
- **A state change resets hitboxes and their victim lists.** To carry victims from one phase to the next (a projectile
  that stops after a hit and must not hit that victim again), stay in the state and change the live hitbox's numbers.
- **Shields push back:** something meant to grind a shield has to keep pressing forward, or the first hit's pushback
  leaves it out of reach.

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
