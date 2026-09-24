---
name: make-film
description: End-to-end workflow for making a new film in this repo: song or narration, cue sheet, storyboard, look development, a parallel build, review rounds, and exports. Use when the user asks for a new music video, animated short or explainer, or to start a new project in projects/.
---

# Make a film

The method and hard-won rules are in `docs/CRAFT.md`. Read §0, §4, §7 and the lesson section closest to your format first. This skill is the order of operations.

## 0. Frame it (with the user)
- Pitch the concept in a few lines: the idea, the look, the format (16:9 or 9:16) and the length. Ask only the questions whose answers change the plan: format, language, narration, any video-model use (off by default), and credit/branding.
- Research reference works when the genre has conventions (e.g. idol MVs): spawn a research agent for the case studies.

## 1. Sound first, because it is the clock
- **Song:** write the lyrics and a composition plan (`projects/<film>/song/plan.json`, section chunks with styles). Generate 4–7 takes with `tools/music.py`, at most 2 at a time.
  - **Choose on evidence:** `audio_analyze.py` (grid fit), `lyric_check.py` (intelligibility), then Gemini. Use blind shuffled rankings or independent rubric scores; never trust one comparative pass.
- **Narration:** verify every fact first. Audition voices with `tools/tts.py` (score them independently, because Gemini has position bias), then speech-to-text the final lines.
- **Cue sheet:** `audio_analyze.py --cues assets/cues.json`, then `cues.js`, plus `songmap.py` so you can see the song.

## 2. Storyboard
Write `STORYBOARD.md` as a shot table: times cut to beats or sung words, the lyric, the event, the camera, the lyric slot and the transition out. Every shot needs an event. Decide the lyric system globally (sizes readable on a phone).

## 3. Look development before shots
- Build look boards as `LOOPS` in `src/board.js` and review them with `--loop=name --stills=0.3`.
- **Characters:** generate a style-target sheet first, code the puppet to match it, and review a model-sheet loop. Build pose presets. Keep the puppet API stable.
- **Illustrated keys (if used):** single-figure references on flat `#00FF00`, reviewed on a contact sheet, rejects regenerated, keyed with `tools/chroma.py`.
- **Video cut-ins (only with sign-off):** image-to-video with `tools/seedance.py`, from a code-rendered start frame to an illustrated end frame on the same background, one request at a time.

## 4. Scaffold, then build in parallel
- Wire `index.html`, `src/film.js` (the cut table with slates for unbuilt shots, plus the lyric overlay) and one stub file per section, all loaded in order.
- Render a slate animatic, then fork one agent per section file. Each owns only its file, reports shared bugs, and reviews its own sheets and strips (at least three passes). Give each a clear brief: the shots, the key sung times, the seams, and the quality bar.

## 5. Review rounds
- **Render and critique:** `--frames --workers=6 --clean`, `--encode`, then a Gemini watch-through, plus your own `--shots` sheet and seam sheets.
- **Verify before fixing:** confirm every claim at full resolution, because critics hallucinate.
- **Revise:** batch the shared fixes yourself, then send each section agent its notes. Repeat until the notes are polish.

## 6. Sound design, exports, publish
- Build a sound-design layer timed to the picture's own schedules and mix it (`sound.py` → `assets/mix.wav`).
- **Exports:** a master (`--crf=15`), a platform file (X: about 14 Mbps), and a vertical template clip for the hook if the film has one.
- **Publish only when the user asks:** scan the git history for keys, commit, push, and attach videos to a GitHub release (files over 100 MB can't go in git).
- Update the README, and add any new lessons to `docs/CRAFT.md`.
