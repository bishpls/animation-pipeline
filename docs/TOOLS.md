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
| `three/vrm.js` | a VRM in three.js (WebGPU or WebGL2) as a pure function of time: `V3.renderer`, `load`, `retarget` (canonical clip onto the normalized humanoid), `performer` (fixed-step springs, face track), `warm`, Blender-style cameras |
| `three/charkit/look.js` | charkit's look on our own export (`charkit/gltf.py`): TSL materials for toon3, the SDF face, hair (ring, gradient, strands), eye plates, inverted hulls with per-vertex width, eyes through the fringe, bloom, debug views (`CK.load`, `CK.pipeline`, `CK.camera`) |
| `pop.js` | the chibi register's kit for plain mode: `shp`, backgrounds (sunburst, checker, dots, speed lines), `pop` type, sparkles, `rig()` strip-warp for keyed illustrations (HELLO, WORLD!, TSUZUKU) |
| `puppet.js` | jointed cut-paper shadow puppets (Reiniger): traced silhouettes pinned at rivets, cut-outs punched through (TSUZUKU's paper world) |
| `warp.js` | draw a canvas through a deformed WebGL2 mesh: paper that bends, cards that breathe |
| `rig.js` | a Live2D-style mesh runtime for layered illustrations: head displacement tables, neck, body shear and bend, FK arms with depth order, pelvis and feet, drawn views, variants, springs, `RIG.perform` coupling |
| `moves.js` | a dance vocabulary and choreography compiler over `rig.js` channels: `MOVES.choreo`, `follow` (springs), `lips`, `blinks`, `hands`, `hop` |
| `plate.js` | image-sequence plates on the film clock (a game capture, footage rendered elsewhere), loaded on demand: `plate(dir, {n, fps, t0})`, `.draw(X, t, ...)`; headless renders await each frame (`window.PREFRAME`) and refuse to draw a neighbour (FRAME PERFECT) |
| `edit.js` | plates in an edit (load after `plate.js`): `keyedPlate(dir, n, {keyed, pre})`, `drawPlate`, `drawKeyed` (a two-pass keyed pair over anything: out = colour + (1 - a) · X), `keyedOutline` (bodies only: the matte thresholded before dilation), `tmap` time maps (velocity ramps, freezes, replays), `stutter`; preloading follows what is drawn (the frame runs once in record mode, then exactly those plate frames load) (SO BACK) |
| `hardedit.js` | the hard-edit grammar for plain mode: `scene`/`present` (draw a shot into a buffer, grade it once), `zoomAt`, `punch` (zoom punches), edge-safe `rgbSplit` (`HARDEDIT.split` scales a film's splits), `NEG` (the one-frame negative impact frame), `grain`, `vignette`, `lastHit` (SO BACK) |
| `meleetype.js` | Melee's own text, extracted from the disc (`tools/machinima/melee/type/`): `MT.load(base)`, `mword` (the game's word graphics: Game!, Go!, Ready, Success!...), `mtext` (its menu font in the word graphics' dress: outline, inner stroke, streaked gradient, shadow), `mname` (results name plates), `mdigits` (HUD damage digits) (SO BACK) |

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
| `vox.py` | sing with a voice bank (found speech as a vocal line, every sound the original recording): `sing` (hard-tuned PSOLA onto notes per syllable, fitted to lengths), `stutter`, `repeat`, `tape_stop`, `pitch_shift` (plain or formant-shifted), `gate`, `to48k` (12 kHz banks lifted with a gentle exciter), `shelf`, `line`, `place`. Keep syllables within about 5–7 semitones of their recording (SO BACK) |
| `hf0.py` | F0 for shouted, processed, reverberant speech (harmonic sum with a half-harmonic penalty, then Viterbi), where Praat and pyin octave-jump (SO BACK) |
| `mixkit.py` | a final mix's helpers (48 kHz stereo): `tape_stop` (speed 1 → 0, pitch falling with it), `duck` (sidechain under a vocal), `carve` (a dynamic-EQ dip at given times), `sections` (music level by section), `limit` (lookahead peak limiter), `decode`, `stem` (SO BACK) |
| `songseat.py` | seat a take on a picture already locked to a grid: align its first downbeat, then cut or pad inside a quiet section so its drop lands on the picture's drop; `--probe T` prints loudness and onsets to find the real downbeat (SO BACK) |
| `songscreen.py` | screen takes before listening: grid phase per section, the drop onset, key per section, and a harshness proxy (energy above 4 kHz, flatness) (SO BACK) |

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
| `machinima/dolphin.py` | Dolphin as a headless plate renderer: isolated pinned profile (`DOLPHIN_USER`, one per capture lane), immediate XFB (no lost frames), one PNG per game frame, DSP audio, the game's OSReport log |
| `machinima/plates.py` | plates between the director's slates (refused if a frame is missing), display aspect, the game audio cut between the slate clicks |
| `machinima/melee/build.py` | a film's choreography -> the director's tables -> the Melee decomp's non-matching build (every hook applied to a stock decomp, behind `#ifndef MUST_MATCH`) -> main.dol; an exclusive lock serialises builds so several capture lanes (a disc folder each) can capture at once |
| `machinima/melee/director/` | the director compiled into Melee: match setup (portrait projection via `aspect`, CPU players, stock matches with the HUD, GAME! and results), boot modes and menu pads (closed-loop CSS token steering), scripted pads, free camera, freeze, closed-loop approach and tech (fast fall, L-cancel, low laser), the `glass` (screen-KO camera), `gamecam` and `shield` cues, hit/laser/state/hitbox/attribute logs |
| `machinima/melee/dsl.py` | the choreography language: moves timed to their hit frame, waveshine and multishine, wavedash, DI, camera keys and tracking, `menu_hold` (e.g. the victory pose by held button), `reset(fresh=True)` (clear stale moves: opt-in, so older films reproduce) |
| `machinima/melee/report.py` | every intended hit against the logged one (frame and beat error); `--fix` the timing solve, `--calib` measured frame data |
| `machinima/melee/timeline.py` | a run as per-fighter action timelines per labelled segment |
| `machinima/prep_plates.py` | capture -> edit-ready plates: slate mode trims between the director's slates (refused if off by one), writes portrait or 16:9 JPEGs, keyed pairs with an LA alpha matte, the game audio cut to the plates, and `info.json` with each hit on the frame it is drawn; raw mode does any folder of frames |
| `machinima/vplate.py`, `dmatte.py`, `key.py`, `vsheet.py` | portrait plates from a 9:16-projection capture (`aspect`; `crop` keeps the HUD); the exact difference matte from a black and a grey-96 pass (additive glows kept; composite `black + (1 - a) · BG`); a single-pass chroma key for comparison; contact sheets of raw captures |
| `machinima/platesfx.py` | a film's game-sound stems from its picture's SFX cue list (`--eval`): each cue cut from its plate's own `audio.wav` and levelled against the song around it, one stem per bus |
| `machinima/melee/ssm.py` | Melee's sound banks (DSP-ADPCM `.ssm`) to WAVs: the announcer, SFX, voices |
| `machinima/melee/type/` | Melee's own text from the disc (the word graphics, the SIS menu font from `main.dol`, HUD digits, name plates) plus a manifest for `engine/meleetype.js` |

Game data (disc images, the game's executable, builds, captured plates, raw game audio) never enters the repo: it lives in
`~/games/` or under gitignored paths.

## 3D motion (the plan is docs/PIPELINE_3D.md; the first character is projects/clawd3d)

| tool | what |
|---|---|
| `mocap3d/gemx_remote.sh` | NVIDIA GEM-X on the GPU box: push directed reference clips, run it static-camera, convert, pull back canonical clips (`--install` once per box). About 2 min and 9.3 GB of VRAM per 5 s clip on an L4 |
| `mocap3d/soma_clip.py` | GEM-X output to the canonical clip (`<name>.clip.npz`: SOMA 77 joints, T-pose-relative rotations, metric root, foot contacts, floor locked) and a BVH; `--check` (npz FK vs BVH), `--qa DIR` (foot slide, swaps, bone lengths, root range) |
| `charkit/gltf.py` (`python -m charkit export BUILD.blend`) | our own glTF 2.0 / VRM 1.0 writer for a built character: meshes as Blender renders them, sparse morph targets from every shape key, T-pose nodes over the A-pose bind, the `OPENADS_charkit_look` extension (every material's look), MToon fallbacks, VRM expressions and lookAt from our keys (docs/CHARKIT.md §7) |
| `projects/charkit-look` | the inspector (`render.mjs projects/charkit-look --serve`: orbit, debug views, parts, expressions, keys, gaze, bones, light, pick, the QA report) and the boards: Blender's build boards next to our WebGPU look with the difference (`--loop=views`, `body`, `expr`, `mouth`, `debug`, `mtoon`, `hook`, `turn`) |
| `gltf_validate.mjs` | the Khronos glTF validator on a .glb / .vrm (`node tools/gltf_validate.mjs FILE`) |
| `charkit/geom` (`python -m charkit.geom ...`) | the geometry kernel (docs/GEOM.md): mesh IO with glTF colours, repair and health reports, a BVH (nearest, winding number, rays), voxel solids / SDFs / marching cubes / grid booleans, exact booleans (manifold3d), Taubin and bilateral smoothing, envelope normals, isotropic remesh, quadric decimation, a numpy rasteriser; `extract SPEC --part hair,skirt` cuts a generated character's hair or skirt into one closed surface (`charkit build --hair geom` uses it) |
| `projects/clawd3d/build/motion.py` | posing and retargeting in armature space: calibration in the source rest pose (hands by their knuckle line), anchor time-warps, springs for secondary motion, floor lock from contacts |

## GPU box (infra/gcp: CUDA-only models; the plan is docs/PIPELINE_3D.md)

| tool | what |
|---|---|
| `tools/worktree.sh` | a sparse worktree: `NAME [--branch B] [--from REF] [--profile core\|charkit\|full] [PATH ...]` (profiles in `charkit/sparse.py`), `--add PATH` to check out more, `--slim` to narrow an existing one |
| `infra/gcp/gpu.sh` | `up` (start and wait for boot), `ssh [cmd]`, `push` / `pull` (to `/srv/work/`), `status`, `stop`; it stops itself after 30 idle minutes (`touch /srv/work/.keepalive` covers a long download) |
| `infra/gcp/gpu-provision.sh` | creates the box once: its own VPC (IAP SSH in, NAT out, no external IP), a service account limited to its bucket and logs; prints the plan, `--execute` runs it |
| `infra/gcp/gpu.env.example` | the config; copy to `gpu.env` (gitignored) |
| `imageto3d/trellis_remote.sh` | TRELLIS.2 image-to-3D on the box (`--install` once): several samples per model load, seeds (identical seed, identical field; `--repeat N`), multi-view samples of one object (`front.png+left.png`, the first the primary; `--mv stochastic` a view per step, the default, or `multidiffusion`), `--no-tex` for shape only (about half the time). Writes GLBs, `<tag>_field.npz` and run.json (stage timings, VRAM, latent statistics) to `charkit/out/i3d/<job>`. About 75 s a full-body sample on the L4 (41 s generation), 6 min a head crop filling the cube |
| `imageto3d/trellis_ext/` | our TRELLIS.2 extension, wrapping the upstream clone unedited: `pipeline.py` (box: staged run, multi-view, field capture), `field.py` (the field file: the shape decoder's surface voxels at the final resolution with dual vertices, edge-crossing logits and split weights, and the texture decoder's PBR attributes on the same voxels; reader, raw mesh, dense solid and signed distance, previews, `A.npz B.npz --out` comparison sheets), `parts.py` (`FIELD.npz [--res 256]`: hair / skin / garment / other label volume and per-part closed surfaces as PLY, with their health; numpy, scipy, scikit-image) |

## Review and bookkeeping
| tool | what |
|---|---|
| `filmscan.py` | frame-difference scan of a rendered film: every unplanned pop or jump, minus the known cuts |
| `gemini.py` | a second opinion on any media file. As a critic it has been usually wrong on specifics (SO BACK: about one claim in four held up; rankings showed pure position bias): a pointer at most (docs/REVIEW.md) |
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
| `projects/so-back/src/captions.js` | lyric captions built from the vocal build's own event list (one clock): words grouped into phrases by kind, one style per kind, a slot per shot (`{cap: {y, x, size, hide, skip, [kind]: {...}}}`), and `captionsIn` to draw words inside a shot's scene (behind a keyed subject) |
| `projects/so-back/src/fields.js` | Y2K / hyperpop fields behind keyed subjects: a racing perspective checker floor, a chrome sky with sparkles, sunbursts, speed-line bursts |
| `projects/so-back/vocals/` (`splice.py`, `words.py`, `judge.py`, `arrange.py`) | a voice bank's phone inventory and new words spliced from its phones (correlation-adaptive crossfades, PSOLA to a template contour), judged by Whisper free and forced choice and seam percentiles; an arrangement placed on beats with per-section levels and reverb sends |
