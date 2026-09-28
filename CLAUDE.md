# animation-pipeline: working here

A base of operations for multimedia films made with Claude Code: songs, animation, sound, all authored in code.
Read `docs/CRAFT.md` before starting or reviewing a film. It is the method, and it holds the hard-won rules.
To start a new film, use the `make-film` skill (`.claude/skills/make-film/`).

## Rules
- **Every frame is authored in code**, a pure function of time. Image models make references, and on request keyed
  illustrations that code rigs and animates.
- **Video-generation models are off by default.** EMBER III's Veo take was judged slop. Use one only with the user's
  explicit sign-off for that film, and only for short cut-ins code can't match. Bridge from a code-rendered start frame
  to an illustrated end frame, and run it one request at a time (`tools/seedance.py`; see CRAFT §11).
- **One clock:** the picture locks to `projects/<film>/assets/cues.json` (from `tools/audio_analyze.py`).
- **Look at your work:** render contact sheets, strips and crops, open them, and fix what you see. Then watch full-length
  passes. Verify any AI critic's claim at full resolution before acting on it.
- **Keys:** `.env` holds ELEVENLABS_API_KEY, GEMINI_API_KEY and OPENAI_API_KEY; `.env.local` holds HF_KEY (Higgsfield). Both are
  gitignored. Never print or commit them. Log paid calls to `tools/ledger.jsonl`.
- **Git:** commit with the user's identity. Never push or publish without asking. Scan the full history for keys before
  any push.

## Layout
- `engine/`: the shared engine: `core.js` (time, easing, beat clock, boil), `riso.js` (the print press), `type.js` (variable-font
  kinetic type), `studio.js` (timeline; riso mode or plain Canvas2D mode via `PROJECT.plain`), `render.mjs`, `pop.js` (the chibi kit
  for plain mode), `puppet.js` (cut-paper puppets), `warp.js` (mesh-warped canvases), `rig.js` (the mesh rig runtime), `moves.js`
  (dance moves and choreography), `plate.js` (image-sequence plates, e.g. game captures), plus the vendored fontkit and fonts (all OFL;
  check glyph coverage before using symbols like ✦ ☆).
- `tools/`: every tool, with its usage, is indexed in `docs/TOOLS.md`. The ones used on every film:
  - `music.py`: ElevenLabs songs, with word timestamps and a stored song_id for inpainting
  - `audio_analyze.py`: beat grid, seams, the cue sheet
  - `lyric_check.py`: speech-to-text diff against the lyrics
  - `songmap.py`: spectrogram and lyric map of a song
  - `tts.py`: narration, with word timestamps
  - `sfx.py`: sound effects; `sfxmix.py`: the SFX stem from the picture's cue list, mixed over the song
  - `gemini.py`: media critic
  - `imagegen.py`: references and keys (`--size 2K`); `gptimage.py`: rig art and pose edits
  - `chroma.py`: flat-green keys to transparent PNG; `rigkit.py`: register, colour-match and composite drawings in rig builders
  - rigs, motion and checks: `segment.py`, `layers.py`, `rigbuild.py`, `variants.py`, `restcheck.py`, `romrun.py`, `motion_audit.py`,
    `dance_audit.py`, `posetrack.py`, `retarget_mocap.py`, `vocalenv.py`, `filmscan.py`
  - `seedance.py`: Higgsfield Seedance 2.5, text-to-video and image-to-video
  - `machinima/`: decompiled games as a film backend (Melee via doldecomp + Dolphin; `tools/machinima/README.md`). Game data
    (disc images, builds, plates) never enters the repo.
- `docs/`: `CRAFT.md` (the method and its lessons), `TOOLS.md`, `RIGGING.md`, `MOTION.md`, `REVIEW.md`, `SESSIONS.md`; `research/`
  (measured Live2D coupling); `references/`: prior art. `PIPELINE_3D.md`: the 3D pipeline plan (mocap, characters, camera conte,
  licences read as commercial, build order).
- `infra/gcp/`: the GPU research box for CUDA-only models (`gpu.sh up | ssh | push | pull | stop`); its config `gpu.env` is
  gitignored because this repo is public. Research repos run there, never on the laptop.
- `projects/<film>/`: `index.html` (script order is the film), `src/` (look, characters, lyrics, `shots/`), `assets/`, `STORYBOARD.md`,
  `board/` (review images, gitignored), `out/` (renders, gitignored).
  - `open-all-night`: riso, 16:9
  - `words-are-fossils`: letterpress, 9:16
  - `hello-world`: plain Canvas2D chibi plus sakuga cut-ins, 16:9
  - `tsuzuku`: plain Canvas2D paper theatre plus a mesh-rigged idol stage, 16:9; the whole film is `--loop=film`
  - `t`: riso, 9:16, one function of time (`make.sh` rebuilds it)
  - `frame-perfect`: a Melee machinima, 16:9 at 60 fps; plates from `tools/machinima`, composited in plain mode
  - `so-back`: a Melee hyperpop hard edit, 9:16 at 60 fps; plates from its own pinned machinima kit (portrait, two-pass keyed),
    announcer-spliced vocals, Melee's own type; the release slice is the `so-back` branch
  - `clawd3d`: TSUZUKU's Clawd as a 3D cel character (headless Blender) and the first 3D mocap dance test (docs/PIPELINE_3D.md phase 1)
- `legacy/ember/`: reusable code from the EMBER shorts.

## Commands (from repo root; P = projects/<film>)
```bash
node engine/render.mjs P --shots --per=3                 # the whole film at a glance
node engine/render.mjs P --sheet=31.2,32.1 --w=640       # chosen times        (--crop=x,y,w,h for detail)
node engine/render.mjs P --strip=30.8:31.4               # every frame of a moment
node engine/render.mjs P --loop=chars --stills=0.3       # a standalone board (model sheets, look tests)
node engine/render.mjs P --eval='LINES.length'           # inspect page state
node engine/render.mjs P --frames --workers=6 --clean && node engine/render.mjs P --encode [--from=s] [--crf=15]
.venv/bin/python tools/romrun.py P                      # a rig's range of motion, every frame checked
.venv/bin/python tools/filmscan.py P/out/frames --known 9.0,12.7   # pops and jumps across a rendered film, minus known cuts
node engine/render.mjs P --serve                         # scrub with sound in Chrome
RENDER_EXACT=1 node engine/render.mjs P --stills=5,30   # bit-exact (CPU canvas) stills, for A/B identity checks (docs/REVIEW.md)
```
