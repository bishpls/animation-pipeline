# Tools: what's in the repo and when to reach for it

Every reusable piece of the pipeline, grouped by stage. Run from the repo root. Each tool's docstring has the full usage.
The method behind them is in `docs/CRAFT.md`, `docs/RIGGING.md`, `docs/MOTION.md`, `docs/REVIEW.md` and `docs/SESSIONS.md`.

**Environments.** `.venv/` is the main one (numpy, scipy, soundfile, librosa, pillow, opencv, requests). `.venv-pose/` holds
MediaPipe 0.10.14 for `posetrack.py` (1.0 crashes on this Mac). `vendor/seed-vc/.venv/` holds SAM 2.1 and Seed-VC for `segment.py`
and `revoice.py` (GPL tool, never committed). **Keys:** `.env` and `.env.local` (CLAUDE.md). Every paid call is appended to
`tools/ledger.jsonl`.

## engine/ (loaded as plain scripts by a project's index.html; everything is global on purpose)
| file | what |
|---|---|
| `core.js` | time, easing (`E.*`), `kf()` keyframes, `spring`, hash noise, boil (`BF`, `jit`), the beat clock (`beatPos`, `barT`, `pulse`, `loud`) |
| `riso.js` | the risograph press: ink layers (`paint`, `ink`, `knock`), halftone tints, misregistration, paper |
| `type.js` | variable-font kinetic type via fontkit (`shape`, `drawText`, `fitShape`); check glyph coverage before using symbols |
| `studio.js` | the timeline (`shots`, `LOOPS`, `PROJECT.overlay`); `PROJECT.plain = true` skips the press for plain Canvas2D |
| `render.mjs` | headless Chrome: stills, sheets, strips, crops, `--eval`, `--serve`, parallel resumable `--frames`, `--encode` |
| `pop.js` | the chibi register's kit for plain mode: `shp`, backgrounds (sunburst, checker, dots, speed lines), `pop` type, sparkles, `rig()` strip-warp for keyed illustrations (HELLO, WORLD!, TSUZUKU) |
| `puppet.js` | jointed cut-paper shadow puppets (Reiniger): traced silhouettes pinned at rivets, cut-outs punched through (TSUZUKU's paper world) |
| `warp.js` | draw a canvas through a deformed WebGL2 mesh: paper that bends, cards that breathe |
| `rig.js` | a Live2D-style mesh runtime for layered illustrations: head displacement tables, neck, body shear and bend, FK arms with depth order, pelvis and feet, drawn views, variants, springs, `RIG.perform` coupling |
| `moves.js` | a dance vocabulary and choreography compiler over `rig.js` channels: `MOVES.choreo`, `follow` (springs), `lips`, `blinks`, `hands`, `hop` |
| `plate.js` | image-sequence plates on the film clock (a game capture, footage rendered elsewhere), loaded on demand: `plate(dir, {n, fps, t0})`, `.draw(X, t, ...)`; headless renders await each frame (`window.PREFRAME`) and refuse to draw a neighbour (FRAME PERFECT) |

## Song, voice and sound
| tool | what |
|---|---|
| `music.py` | ElevenLabs Music: compose from a composition plan; keeps audio, word timestamps and the song_id for inpainting |
| `audio_analyze.py` | beat grid, seams and the cue sheet (`assets/cues.json`): the one clock; `--downbeat S` pins the grid to a measured downbeat when a syncopated kick fools the tracker (FRAME PERFECT's came out 0.8 s late) |
| `lyric_check.py` | speech-to-text (Scribe) diffed against the intended lyrics |
| `songmap.py` | spectrogram, loudness, sections, bars and lyrics on one image: see the song |
| `stems.py` | ElevenLabs stem separation; `--pitch` prints a vocal's range |
| `tts.py` | narration and spoken lines with character timestamps |
| `revoice.py` | Seed-VC singing voice conversion (tried on TSUZUKU and rejected by ear: CRAFT §9) |
| `sfx.py` | one ElevenLabs sound effect |
| `sfxmix.py` | a film's SFX stem: the cue sheet dumped from the picture (`--eval`), each cue leveled against the song around it, no ducking; writes cues.json, the stem and the mix |
| `vocalenv.py` | a vocal stem's loudness envelope in song time (held-note lip-sync: `MOVES.lips` reads it) |

## Images and rigs
| tool | what |
|---|---|
| `gptimage.py` | GPT Image: rig art, pose edits, companion drawings (beat Gemini on an A/B for rig art) |
| `imagegen.py` | Gemini image: references and style targets |
| `chroma.py` | flat-green key to RGBA with despill; crops by default, `--full` keeps the canvas; `from chroma import key` in a builder |
| `rigkit.py` | a builder's helpers: ECC `register` on a fit mask, `residual`, `colour_match`, `feather`, `blend`, `over`, `bleed`, `poly`, `shift` |
| `register.py` | align one edited drawing to the base on an ROI that shouldn't change (CLI) |
| `segment.py` | SAM 2.1 part masks (points and boxes per part), masks only |
| `layers.py` | cut an illustration into rig layers along its own drawn lines (cells vote by mask) |
| `rigbuild.py` | underpaint what motion can reveal (companion drawings first, invented fills last and marked) and export the manifest `rig.js` loads |
| `variants.py` | drawn variants of face and hand patches (blinks, visemes, hand shapes) as registered crops |
| `armpose.py` | drawn arm poses where the mesh can't make an arm read |
| `restcheck.py` | invariant: the rig at rest reproduces the illustration (heat map of any difference) |
| `romrun.py` | one-command range-of-motion check: renders the ID pass of `src/rom.js`, checks every frame, sheets the worst (`romcheck2.py` does the checking) |
| `romheat.py` | heat maps of where a ROM run's problems happen |
| `holes.py` | holes in a rig test rendered on magenta (background showing through the character) |

## Motion and mocap
| tool | what |
|---|---|
| `motion_audit.py` | a choreography measured against motion principles: stillness, core range, overlap lags, accents vs drums, energy vs song, arcs, springs |
| `dance_audit.py` | per phrase: mocap coverage, held-pose clusters, hand shapes and swaps, turned-view shapes, airborne frames |
| `phrase_metrics.py` | before/after metrics per phrase from two dumps, plus planted-foot slide and dip phase |
| `leg_metrics.py` | per-bar travel, steps and foot slide from a channel dump |
| `drawings.py` | every drawing of every move side by side (before, in-between, past, pose, hold) |
| `posetrack.py` | MediaPipe pose landmarks per frame from a reference clip (`.venv-pose`) |
| `retarget_mocap.py` | pose track to rig channel curves, time-warped onto the beat grid by structural anchors |
| `mocap_phrases.py` | rebuild every retargeted phrase in a film's `refs/mocap/phrases.json` |
| `mocap_sheet.py` | contact sheet and wrist/hip plot of a tracked clip, to judge a generation |
| `mocap_diagnose.py` | where a retargeted clip runs out of rig (targets against clamps) |
| `seedance.py` | Higgsfield Seedance 2.5; **off by default** (CLAUDE.md): only with the user's sign-off, one request at a time |

## Game machinima (tools/machinima: decompiled games as a film backend; setup, controls and lab findings in its README)

| tool | what it's for |
|---|---|
| `machinima/dolphin.py` | Dolphin as a headless plate renderer: isolated pinned profile, one PNG per game frame, DSP audio, the game's OSReport log |
| `machinima/plates.py` | plates between the director's slates (refused if a frame is missing), display aspect, the game audio cut between the slate clicks |
| `machinima/melee/build.py` | a film's choreography -> the director's tables -> the Melee decomp's non-matching build (hooks behind `#ifndef MUST_MATCH`) -> main.dol |
| `machinima/melee/director/` | the director compiled into Melee: match setup, scripted pads, free camera, freeze, closed-loop approach and tech (fast fall, L-cancel, low laser), hit/laser/state logs |
| `machinima/melee/dsl.py` | the choreography language: moves timed to their hit frame, waveshine and multishine, wavedash, DI, camera keys and tracking |
| `machinima/melee/report.py` | every intended hit against the logged one (frame and beat error); `--fix` the timing solve, `--calib` measured frame data |
| `machinima/melee/timeline.py` | a run as per-fighter action timelines per labelled segment |

Game data (disc images, the game's executable, builds, captured plates, raw game audio) never enters the repo: it lives in
`~/games/` or under gitignored paths.

## 3D motion (the plan is docs/PIPELINE_3D.md; the first character is projects/clawd3d)

| tool | what |
|---|---|
| `mocap3d/gemx_remote.sh` | NVIDIA GEM-X on the GPU box: push directed reference clips, run it static-camera, convert, pull back canonical clips (`--install` once per box). About 2 min and 9.3 GB of VRAM per 5 s clip on an L4 |
| `mocap3d/soma_clip.py` | GEM-X output to the canonical clip (`<name>.clip.npz`: SOMA 77 joints, T-pose-relative rotations, metric root, foot contacts, floor locked) and a BVH; `--check` (npz FK vs BVH), `--qa DIR` (foot slide, swaps, bone lengths, root range) |
| `projects/clawd3d/build/motion.py` | posing and retargeting in armature space: calibration in the source rest pose (hands by their knuckle line), anchor time-warps, springs for secondary motion, floor lock from contacts |

## GPU box (infra/gcp: CUDA-only models; the plan is docs/PIPELINE_3D.md)

| tool | what |
|---|---|
| `infra/gcp/gpu.sh` | `up` (start and wait for boot), `ssh [cmd]`, `push` / `pull` (to `/srv/work/`), `status`, `stop`; it stops itself after 30 idle minutes (`touch /srv/work/.keepalive` covers a long download) |
| `infra/gcp/gpu-provision.sh` | creates the box once: its own VPC (IAP SSH in, NAT out, no external IP), a service account limited to its bucket and logs; prints the plan, `--execute` runs it |
| `infra/gcp/gpu.env.example` | the config; copy to `gpu.env` (gitignored) |

## Review and bookkeeping
| tool | what |
|---|---|
| `filmscan.py` | frame-difference scan of a rendered film: every unplanned pop or jump, minus the known cuts |
| `gemini.py` | a second opinion on any media file; a noisy critic (docs/REVIEW.md) |
| `production_stats.py` | reproducible production numbers for a making-of: tokens, paid calls, commits, assets |

## Project kits worth promoting on their second use (CRAFT §11)
These live with the film that made them. Promote one to `engine/` or `tools/` when a second film needs it, as `pop.js` was.
| where | what |
|---|---|
| `projects/tsuzuku/src/idolstage.js` | an idol stage: LED screens and dot rasterizing, the MV post-FX (beat punch, afterimages, glitch, colour fringe), and lyric placement that never splits a phrase behind a performer |
| `projects/tsuzuku/src/motionlab.js` | `MOTIONLAB.dump` (the dump format the motion tools read) and `MOTIONLAB.groove` (the core-bounce layer; docs/MOTION.md) |
| `projects/tsuzuku/src/fableseat.js` + `rig/fable_seated/build.py` | a drawn pose-set character: pose edits registered on a base and cut into patches, swapped on twos, with book masks and quads for printing onto a page |
| `projects/tsuzuku/src/fableroom.js` + `rig/fable_room/` | drawings that walk on planted feet (`feet.py` finds each geta's pivot tooth) |
| `projects/tsuzuku/src/paper.js` | the paper-theatre look: light through a sheet, cellophane gels, and the `PAPER_SFX` cue registry |
| `projects/tsuzuku/src/film.js` | a whole film dispatched over section loops, each on its own local or song clock |
| `projects/tsuzuku/src/rom.js` | a range-of-motion matrix (`window.ROM`) for `romrun.py` |
| `projects/tsuzuku/rig/fable/cut.py`, `rig/clawd_paper/cut.py` | cut-paper puppet builders for `engine/puppet.js` (trace, capsule limbs, rivets) |
| `projects/tsuzuku/voice/record.py` | spoken takes fitted to their windows by tightening internal pauses, never by stretching |
| `projects/tsuzuku/src/crabs.js` | the mascot troupe (a renamed copy of HELLO, WORLD!'s `clawd()`) |
| `projects/hello-world/src/film.js` | `cutin`, `loadSeq`, `seqDraw` (illustrated and video cut-ins time-remapped to the music), karaoke and call stamps |
| `projects/hello-world/build_lyrics.py` | lyric lines aligned to sung word times, written as `lyrics.js` |
| `legacy/ember/` | the EMBER shorts' synth and mastering engine, IK, follow-through, sakuga FX |
