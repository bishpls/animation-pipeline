# animation-pipeline: working here

A base of operations for multimedia films made with Claude Code: songs, animation, sound, all authored in code.
Read `docs/CRAFT.md` before starting or reviewing a film. It is the method, and it holds the hard-won rules.

## Rules
- **No video-generation models.** Every frame is code, a pure function of time. Image models are for reference only.
- One clock: the picture locks to `projects/<film>/assets/cues.json` (from `tools/audio_analyze.py`).
- Look at your work: render contact sheets, strips and crops, open them, and fix what you see. Then watch full-length passes.
- Keys live in `.env` (gitignored): ELEVENLABS_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY. Log paid calls to `tools/ledger.jsonl`.
- Commit with the user's identity; never push without asking.

## Layout
- `engine/`: shared engine (core, the riso press, type, studio, render.mjs) plus vendored fontkit and fonts.
- `tools/`: music.py (ElevenLabs songs + word timestamps), audio_analyze.py (grid, seams, cue sheet), lyric_check.py (STT diff), songmap.py, gemini.py (media critic), imagegen.py (reference images), sfx.py.
- `projects/<film>/`: index.html (script order = film), src/ (look, cast, world, lyrics, shots/), assets/, STORYBOARD.md, board/ (review images, gitignored), out/ (renders, gitignored).
- `legacy/ember/`: reusable code from the EMBER shorts. `docs/references/`: prior art.

## Commands (from repo root)
```bash
node engine/render.mjs projects/open-all-night --shots --per=3            # the whole film at a glance
node engine/render.mjs projects/open-all-night --sheet=31.2,32.1 --w=640  # chosen times
node engine/render.mjs projects/open-all-night --strip=30.8:31.4          # every frame of a moment
node engine/render.mjs projects/open-all-night --frames --workers=6 && node engine/render.mjs projects/open-all-night --encode
node engine/render.mjs projects/open-all-night --serve                    # scrub with sound in Chrome
```
