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
  kinetic type), `studio.js` (timeline; riso mode or plain Canvas2D mode via `PROJECT.plain`), `render.mjs`, plus the vendored
  fontkit and fonts (all OFL; check glyph coverage before using symbols like ✦ ☆).
- `tools/`:
  - `music.py`: ElevenLabs songs, with word timestamps and a stored song_id for inpainting
  - `audio_analyze.py`: beat grid, seams, the cue sheet
  - `lyric_check.py`: speech-to-text diff against the lyrics
  - `songmap.py`: spectrogram and lyric map of a song
  - `tts.py`: narration, with word timestamps
  - `sfx.py`: sound effects
  - `gemini.py`: media critic
  - `imagegen.py`: references and keys (`--size 2K`)
  - `chroma.py`: flat-green keys to transparent PNG
  - `seedance.py`: Higgsfield Seedance 2.5, text-to-video and image-to-video
- `projects/<film>/`: `index.html` (script order is the film), `src/` (look, characters, lyrics, `shots/`), `assets/`, `STORYBOARD.md`,
  `board/` (review images, gitignored), `out/` (renders, gitignored).
  - `open-all-night`: riso, 16:9
  - `words-are-fossils`: letterpress, 9:16
  - `hello-world`: plain Canvas2D chibi plus sakuga cut-ins, 16:9
- `legacy/ember/`: reusable code from the EMBER shorts. `docs/references/`: prior art.

## Commands (from repo root; P = projects/<film>)
```bash
node engine/render.mjs P --shots --per=3                 # the whole film at a glance
node engine/render.mjs P --sheet=31.2,32.1 --w=640       # chosen times        (--crop=x,y,w,h for detail)
node engine/render.mjs P --strip=30.8:31.4               # every frame of a moment
node engine/render.mjs P --loop=chars --stills=0.3       # a standalone board (model sheets, look tests)
node engine/render.mjs P --eval='LINES.length'           # inspect page state
node engine/render.mjs P --frames --workers=6 --clean && node engine/render.mjs P --encode [--from=s] [--crf=15]
node engine/render.mjs P --serve                         # scrub with sound in Chrome
```
